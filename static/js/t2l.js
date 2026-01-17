// T2L Tool Logic (Vanilla JS)

const T2L_CONFIG = {
    brand: window.SELECTED_BRAND || 'VOLKSWAGEN', // Injected from HTML
};

// DOM Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const inputSwb = document.getElementById('input-swb');
const inputChassis = document.getElementById('input-chassis');
const inputDiz = document.getElementById('input-diz');
const btnGenerate = document.getElementById('btn-generate');
const btnClear = document.getElementById('btn-clear');
const errorMsg = document.getElementById('error-msg');
const resultsSection = document.getElementById('results-section');
const btnDownload = document.getElementById('btn-download');

// --- Settings Modal Elements ---
const modalSettings = document.getElementById('modal-settings');
const btnSettings = document.getElementById('btn-settings');
const settingsList = document.getElementById('settings-list');
const btnAddSetting = document.getElementById('btn-add-setting');
const inputSetCode = document.getElementById('set-code');
const inputSetName = document.getElementById('set-name');

// --- HS Modal Elements (Toyota only) ---
const modalHs = document.getElementById('modal-hs');
const btnHsCodes = document.getElementById('btn-hs-codes');
const btnAddHs = document.getElementById('btn-add-hs');
const hsList = document.getElementById('hs-list');
const hsVinInput = document.getElementById('hs-vin-input');
const hsCodeInput = document.getElementById('hs-code-input');

// --- State ---
let uploadedData = null; // JSON from CSV
let mappings = JSON.parse(localStorage.getItem('t2l_mappings')) || [
    { code: 'DEHAM', name: 'HAMBURG' },
    { code: 'BEZEE', name: 'ZEEBRUGGE' },
    { code: 'ESSET', name: 'SETUBAL' },
    { code: 'DEEMD', name: 'EMDEN' },
    { code: 'ESVGP', name: 'VIGO' },
    { code: 'ESSDR', name: 'SANTANDER' },
    { code: 'TRYKC', name: 'YARIMCA' },
    { code: 'FRLEH', name: 'LE HAVRE' },
    { code: 'IEDUB', name: 'DUBLIN' },
    { code: 'GBSHE', name: 'SHEERNESS' },
    { code: 'GBGRI', name: 'GRIMSBY' },
    { code: 'GBTYN', name: 'TYNE' },
    { code: 'BEANR', name: 'ANTWERP' }
];

let hsCodes = JSON.parse(localStorage.getItem('t2l_hs_codes')) || {};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    renderSettings();
    if (T2L_CONFIG.brand === 'TOYOTA') renderHsList();
});

// --- Settings Logic ---
btnSettings.addEventListener('click', () => {
    modalSettings.style.display = 'flex';
});

if (btnHsCodes) {
    btnHsCodes.addEventListener('click', () => {
        modalHs.style.display = 'flex';
    });
}

function renderSettings() {
    settingsList.innerHTML = '';
    mappings.forEach((map, index) => {
        const div = document.createElement('div');
        div.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;';
        div.innerHTML = `
            <span><b>${map.code}</b> = ${map.name}</span>
            <button onclick="removeSetting(${index})" style="background: none; border: none; color: #ff6b6b; cursor: pointer;"><i class="fas fa-times"></i></button>
        `;
        settingsList.appendChild(div);
    });
}

function removeSetting(index) {
    mappings.splice(index, 1);
    saveSettings();
    renderSettings();
}

btnAddSetting.addEventListener('click', () => {
    const code = inputSetCode.value.trim().toUpperCase();
    const name = inputSetName.value.trim().toUpperCase();
    if (code && name) {
        mappings.push({ code, name });
        inputSetName.value = '';
        inputSetCode.value = '';
        saveSettings();
        renderSettings();
    }
});

function saveSettings() {
    localStorage.setItem('t2l_mappings', JSON.stringify(mappings));
}

// --- HS Codes Logic (Toyota) ---
if (btnAddHs) {
    btnAddHs.addEventListener('click', () => {
        const vins = hsVinInput.value.split('\n').map(v => v.trim()).filter(v => v);
        const codes = hsCodeInput.value.split('\n').map(c => c.trim()).filter(c => c);

        if (vins.length !== codes.length) {
            alert('Mismatch! Number of VINs and Codes must match.');
            return;
        }

        vins.forEach((vin, i) => {
            if (vin) hsCodes[vin] = codes[i];
        });

        localStorage.setItem('t2l_hs_codes', JSON.stringify(hsCodes));
        renderHsList();
        hsVinInput.value = '';
        hsCodeInput.value = '';
    });
}

function renderHsList() {
    if (!hsList) return;
    hsList.innerHTML = '';
    const keys = Object.keys(hsCodes);
    if (keys.length === 0) {
        hsList.innerHTML = '<p style="opacity:0.5;">No HS Codes saved.</p>';
        return;
    }
    keys.forEach(vin => {
        const div = document.createElement('div');
        div.className = "flex justify-between items-center p-2 mb-1 bg-white/5 rounded border border-white/10";
        div.innerHTML = `<span class="font-mono text-xs">${vin}: ${hsCodes[vin]}</span> <button onclick="removeHs('${vin}')" class="text-red-400 hover:text-red-300"><i class="fas fa-times"></i></button>`;
        hsList.appendChild(div);
    });
}

window.removeHs = function (vin) {
    delete hsCodes[vin];
    localStorage.setItem('t2l_hs_codes', JSON.stringify(hsCodes));
    renderHsList();
}


// --- Tab Logic ---
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
});

// --- File Handling ---
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.borderColor = 'var(--accent-color)'; });
dropZone.addEventListener('dragleave', (e) => { e.preventDefault(); dropZone.style.borderColor = 'var(--glass-border)'; });
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--glass-border)';
    handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleFile(e.target.files[0]);
});

function handleFile(file) {
    if (file) {
        document.getElementById('file-name').textContent = file.name;
        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: function (results) {
                uploadedData = results.data;
                console.log("CSV Parsed", uploadedData.length);
            }
        });
    }
}

// --- Generation Logic ---
btnGenerate.addEventListener('click', () => {
    errorMsg.style.display = 'none';

    // Validation
    const rawChassis = inputChassis.value.trim().split('\n').map(x => x.trim()).filter(x => x);
    const swb = inputSwb.value.trim();

    if (!uploadedData && T2L_CONFIG.brand !== 'TOYOTA') { // Toyota might not need CSV if just checking HS? Assuming CSV always needed for now
        showError("Please upload a CSV file first.");
        return;
    }
    if (rawChassis.length === 0) {
        showError("Please enter at least one Chassis number.");
        return;
    }

    // Process
    processT2L(uploadedData, rawChassis, swb);
});

btnClear.addEventListener('click', () => {
    uploadedData = null;
    document.getElementById('file-name').textContent = "Upload Stock CSV";
    inputSwb.value = '';
    inputChassis.value = '';
    inputDiz.value = '';
    fileInput.value = '';
    resultsSection.style.display = 'none';
    errorMsg.style.display = 'none';
});

function showError(msg) {
    errorMsg.querySelector('span').textContent = msg;
    errorMsg.style.display = 'flex';
}

function processT2L(csvData, chassisList, swb) {
    // Determine Index Keys from CSV (Dynamic)
    // Common variants: 'Chassis', 'VIN', 'Ident. no.', 'Vehicle ID'
    // 'Destination', 'Dest. Loc.', 'Ship-to'
    // 'Model', 'Mat. Desc.'

    // We'll search one by one
    let chassisKey, destKey, modelKey;

    if (csvData && csvData.length > 0) {
        const keys = Object.keys(csvData[0]);
        chassisKey = keys.find(k => /chassis|vin|ident/i.test(k));
        destKey = keys.find(k => /dest|ship-to/i.test(k));
        modelKey = keys.find(k => /model|mat|desc/i.test(k));
    }

    // Filter Matches
    const matchedItems = [];
    const dizList = inputDiz.value.trim().split('\n').map(x => x.trim()).filter(x => x);

    chassisList.forEach((vin, idx) => {
        let csvRow = null;
        if (uploadedData) {
            csvRow = uploadedData.find(row => row[chassisKey] && row[chassisKey].includes(vin));
        }

        // If Toyota, check HS Code
        let hsCode = '87032319'; // Default
        if (T2L_CONFIG.brand === 'TOYOTA') {
            if (hsCodes[vin]) hsCode = hsCodes[vin];
        }

        matchedItems.push({
            vin: vin,
            diz: dizList[idx] || '', // Match by index if available
            dest: csvRow ? (csvRow[destKey] || '') : '',
            model: csvRow ? (csvRow[modelKey] || '') : '',
            hsCode: hsCode
        });
    });

    displayResults(matchedItems, swb);
}

function displayResults(items, swb) {
    resultsSection.style.display = 'block';
    document.getElementById('success-msg').textContent = `Processed ${items.length} vehicles`;

    // 1. Good Items (C3 / G3)
    // C3 Format: 87032319 (HS)
    // G3 Format: 003(SWB) - 001(ItemNo) - 860.00(Weight placeholder) - VIN - Model - Dest

    const listC3 = document.getElementById('list-c3');
    const listG3 = document.getElementById('list-g3');
    listC3.innerHTML = '';
    listG3.innerHTML = '';

    const listPack1 = document.getElementById('list-pack1');
    const listPack2 = document.getElementById('list-pack2');
    listPack1.innerHTML = '';
    listPack2.innerHTML = '';

    const listDoc1 = document.getElementById('list-doc1');
    const listDoc2 = document.getElementById('list-doc2');
    listDoc1.innerHTML = '';
    listDoc2.innerHTML = '';

    items.forEach((item, i) => {
        const itemNum = String(i + 1).padStart(3, '0');
        const weight = "1000"; // Placeholder weight, maybe configurable later
        const destName = resolveMapping(item.dest);

        // C3
        const rowC3 = document.createElement('div');
        rowC3.textContent = item.hsCode;
        listC3.appendChild(rowC3);

        // G3 
        // Format: SWB - ItemNum - Weight - VIN - Model - Dest(Resolved)
        const rowG3 = document.createElement('div');
        rowG3.textContent = `${swb} - ${itemNum} - ${weight} - ${item.vin} - ${item.model} - ${destName}`;
        listG3.appendChild(rowG3);

        // Packaging
        // A3:B3 = SWB, ItemNum
        const rowP1 = document.createElement('div');
        rowP1.textContent = `${swb} ${itemNum}`;
        listPack1.appendChild(rowP1);

        // D3:E3 = VIN, DIZ
        const rowP2 = document.createElement('div');
        rowP2.textContent = `${item.vin} ${item.diz}`;
        listPack2.appendChild(rowP2);

        // Docs
        // A3:B3 = SWB, ItemNum
        const rowD1 = document.createElement('div');
        rowD1.textContent = `${swb} ${itemNum}`;
        listDoc1.appendChild(rowD1);

        // E3 = DIZ
        const rowD2 = document.createElement('div');
        rowD2.textContent = item.diz;
        listDoc2.appendChild(rowD2);
    });
}

function resolveMapping(rawDest) {
    if (!rawDest) return "UNKNOWN";
    // Check mappings
    const found = mappings.find(m => rawDest.includes(m.code));
    return found ? found.name : rawDest;
}


// --- Copy Functionality ---
document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const targetId = `list-${btn.dataset.copy}`;
        const container = document.getElementById(targetId);
        const text = container.innerText; // Preserves newlines
        navigator.clipboard.writeText(text).then(() => {
            const originalIcon = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => btn.innerHTML = originalIcon, 2000);
        });
    });
});

// --- Download Excel ---
btnDownload.addEventListener('click', () => {
    // Generate simple excel of the results
    const wb = XLSX.utils.book_new();
    const ws_data = [
        ["HS Code", "G3 String", "Pack 1", "Pack 2"]
    ];

    document.getElementById('list-g3').childNodes.forEach((node, i) => {
        const c3 = document.getElementById('list-c3').childNodes[i].textContent;
        const g3 = node.textContent;
        const p1 = document.getElementById('list-pack1').childNodes[i].textContent;
        const p2 = document.getElementById('list-pack2').childNodes[i].textContent;
        ws_data.push([c3, g3, p1, p2]);
    });

    const ws = XLSX.utils.aoa_to_sheet(ws_data);
    XLSX.utils.book_append_sheet(wb, ws, "T2L Data");
    XLSX.writeFile(wb, `T2L_Export_${inputSwb.value || 'data'}.xlsx`);
});
