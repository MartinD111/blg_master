from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import io
from functools import wraps
import os
import datetime
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

# Mock User Data - Added 'avatar'
USERS = {
    'admin': {'password': 'admin', 'role': 'admin', 'name': 'Martin', 'avatar': '👨‍💻'},
    'martin.dumanic@blg.si': {'password': '666666', 'role': 'admin', 'name': 'Martin Dumanic', 'avatar': 'M'},
    'operativa': {'password': 'op', 'role': 'operativa', 'name': 'Operator', 'avatar': '👷'},
    'service': {'password': 'srv', 'role': 'service_admin', 'name': 'ServiceAdmin', 'avatar': '🔧'}
}

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
        
        user = USERS.get(username)
        if user and user['password'] == password:
            # Ensure avatar exists in session
            if 'avatar' not in user: user['avatar'] = '👤'
            session['user'] = user
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')
            
    return render_spa('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/api/update-avatar', methods=['POST'])
@login_required
def update_avatar():
    try:
        data = request.get_json()
        new_avatar = data.get('avatar')
        if new_avatar:
            # Update session
            session['user']['avatar'] = new_avatar
            session.modified = True 
            
            # Update Mock DB (for this session lifecycle only since it's in-memory)
            for k, v in USERS.items():
                if v['name'] == session['user']['name']:
                    USERS[k]['avatar'] = new_avatar
                    break
            
            return jsonify({'success': True, 'avatar': new_avatar})
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
    'toyota': ['Kamioni', 'Ladje', 'Vagoni'],
    'volkswagen': ['Ladje', 'Carinjenje', 'DVH Helper/Tools', 'Stock', 'T2L', 'Kamioni', 'A.TR Extractor', 'Tramak'],
    'vagoni': ['Sledilnik', 'Railway Agency'],
    'others': ['Docs'],
    'ecmr': ['All-in-One Tool'],
    'statistika': ['General Stats'],
    'fakture': ['Billing'],
    'produktivnost': ['Management']
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

if __name__ == '__main__':
    # Print map for debugging if needed
    # print(app.url_map)
    app.run(debug=True, use_reloader=True, port=5000)
