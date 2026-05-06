let academicData = null;
let cleaningData = null;
let currentChart = null;
let cleanChart = null;
let currentFeatureData = null;
let lastFilter = { name: null, label: null };
let icd9Mapping = {};

const MEDICATION_LIST = ['metformin','repaglinide','nateglinide','chlorpropamide','glimepiride','acetohexamide','glipizide','glyburide','tolbutamide','pioglitazone','rosiglitazone','acarbose','miglitol','troglitazone','tolazamide','examide','citoglipton','insulin','glyburide-metformin','glipizide-metformin','glimepiride-pioglitazone','metformin-rosiglitazone','metformin-pioglitazone'];

document.addEventListener('DOMContentLoaded', () => {
    Promise.all([
        fetch('academic_data.json').then(r => r.json()),
        fetch('cleaning_data.json').then(r => r.json()),
        fetch('icd9_mapping.json').then(r => r.json()).catch(() => ({}))
    ]).then(([data, cleaning, mapping]) => {
        academicData = data;
        cleaningData = cleaning;
        icd9Mapping = mapping;
        initRawPage();
        initCleanPage();
    }).catch(err => {
        console.error(err);
        document.body.innerHTML = `<div style="padding:50px;text-align:center;color:red"><h2>Error loading data</h2><p>${err}</p></div>`;
    });

    document.getElementById('toggle-log-scale').addEventListener('change', () => {
        if (currentFeatureData) renderChart(currentFeatureData);
    });
    document.getElementById('table-limit').addEventListener('change', () => {
        showDrillDown(lastFilter.name, lastFilter.label);
    });
    document.getElementById('show-deleted').addEventListener('change', () => renderCleanBrowser());
    document.getElementById('clean-limit').addEventListener('change', () => renderCleanBrowser());
    document.getElementById('clean-feature-search').addEventListener('input', (e) => {
        renderCleanFeatureList(e.target.value);
    });
    document.getElementById('clean-toggle-log').addEventListener('change', () => {
        // Re-render with the currently selected column
        const activeRow = document.querySelector('#clean-feature-tbody tr.active-row');
        if (activeRow) activeRow.click();
    });
});

// ==================== PAGE SWITCHING ====================
function switchPage(page) {
    document.getElementById('page-raw').style.display   = page === 'raw'   ? '' : 'none';
    document.getElementById('page-clean').style.display = page === 'clean' ? '' : 'none';
    document.getElementById('tab-raw').classList.toggle('active',   page === 'raw');
    document.getElementById('tab-clean').classList.toggle('active', page === 'clean');
}

// ==================== PAGE 1: RAW DATA ====================
function initRawPage() {
    const ov = academicData.dataset_overview;
    document.getElementById('overview-rows').textContent    = ov.total_rows.toLocaleString();
    document.getElementById('overview-cols').textContent    = ov.total_cols.toLocaleString();
    document.getElementById('overview-missing').textContent = ov.total_missing_cells.toLocaleString();
    document.getElementById('overview-dupes').textContent   = ov.duplicate_rows.toLocaleString();

    renderFeatureList();
    showDrillDown(null, null);

    document.getElementById('feature-search').addEventListener('input', (e) => renderFeatureList(e.target.value));
}

function renderFeatureList(filter = '') {
    const tbody = document.getElementById('feature-tbody');
    tbody.innerHTML = '';
    Object.keys(academicData.features).forEach(key => {
        if (!key.toLowerCase().includes(filter.toLowerCase())) return;
        const feat = academicData.features[key];
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><strong>${feat.name}</strong></td><td>${feat.missing_pct}%</td><td><span class="action-badge">${feat.cleaning_method}</span></td>`;
        tr.addEventListener('click', () => {
            document.querySelectorAll('#feature-tbody tr').forEach(r => r.classList.remove('active-row'));
            tr.classList.add('active-row');
            currentFeatureData = feat;
            showFeatureDetail(feat);
        });
        tbody.appendChild(tr);
    });
}

function showFeatureDetail(feat) {
    document.getElementById('welcome-message').style.display = 'none';
    document.getElementById('detail-view').style.display = 'block';
    document.getElementById('detail-title').textContent = feat.name;
    document.getElementById('detail-type').textContent  = feat.type;
    document.getElementById('detail-description').textContent    = feat.description;
    document.getElementById('detail-action-title').textContent   = feat.cleaning_method;
    document.getElementById('detail-action-explanation').textContent = feat.cleaning_explanation;

    const statsBody = document.getElementById('detail-stats-tbody');
    statsBody.innerHTML = '';
    [['Missing Count', feat.missing_count.toLocaleString()], ['Missing (%)', feat.missing_pct + '%'], ['Unique Values', feat.unique_count.toLocaleString()]].forEach(([k,v]) => {
        statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
    });
    if (feat.type === 'Numeric' && feat.stats?.mean !== undefined) {
        [['Mean', feat.stats.mean], ['Std Dev', feat.stats.std], ['Median', feat.stats.median], ['Max', feat.stats.max]].forEach(([k,v]) => {
            if (v !== null) statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
        });
    }

    const logToggle = document.getElementById('toggle-log-scale');
    if (feat.distribution?.values?.length > 0) {
        const maxVal = Math.max(...feat.distribution.values);
        const minNZ  = Math.min(...feat.distribution.values.filter(v => v > 0)) || 1;
        logToggle.checked = (maxVal / minNZ > 50);
    }
    renderChart(feat);
}

function renderChart(feat) {
    const ctx = document.getElementById('distribution-chart').getContext('2d');
    if (currentChart) currentChart.destroy();
    if (!feat.distribution?.labels) return;

    const useLog = document.getElementById('toggle-log-scale').checked;
    currentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: feat.distribution.labels,
            datasets: [{ data: feat.distribution.values, backgroundColor: '#0f4c81', barPercentage: feat.type === 'Numeric' ? 1.0 : 0.8 }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            onClick: (e, elements) => {
                if (elements.length > 0) showDrillDown(feat.name, feat.distribution.labels[elements[0].index]);
            },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { title: (ctx) => {
                    const label = ctx[0].label;
                    if (feat.name.startsWith('diag_')) {
                        const key = label.replace('.', '');
                        const desc = icd9Mapping[key] || (Object.keys(icd9Mapping).find(k => k.startsWith(key)) && icd9Mapping[Object.keys(icd9Mapping).find(k => k.startsWith(key))] + ' (category)');
                        if (desc) return `ICD-9 [${label}]: ${desc}`;
                    }
                    if (feat.value_mapping?.[label]) return `ID ${label}: ${feat.value_mapping[label]}`;
                    return label;
                }}}
            },
            scales: {
                y: { type: useLog ? 'logarithmic' : 'linear', beginAtZero: true },
                x: { ticks: { maxRotation: 45 } }
            }
        }
    });
}

function showDrillDown(featureName, valueLabel) {
    lastFilter = { name: featureName, label: valueLabel };
    const title  = document.getElementById('drill-down-title');
    const thead  = document.getElementById('drill-down-thead');
    const tbody  = document.getElementById('drill-down-tbody');
    const limit  = parseInt(document.getElementById('table-limit').value) || 100;

    const filtered = featureName
        ? academicData.raw_sample.filter(row => String(row[featureName]) === String(valueLabel))
        : academicData.raw_sample;

    title.textContent = featureName
        ? `Filtered View: ${filtered.length.toLocaleString()} patients where ${featureName} = ${valueLabel} (Limit: ${limit})`
        : `Clinical Record Browser — ${Math.min(filtered.length, limit).toLocaleString()} of ${filtered.length.toLocaleString()} records`;

    const baseCols = Object.keys(academicData.raw_sample[0]).filter(c => !MEDICATION_LIST.includes(c));
    const allCols  = [...baseCols, 'active_medications'];
    thead.innerHTML = `<tr>${allCols.map(c => `<th>${c.replace(/_/g,' ')}</th>`).join('')}</tr>`;
    tbody.innerHTML = '';

    const renderLimit = Math.min(filtered.length, limit);
    for (let i = 0; i < renderLimit; i++) {
        const row = filtered[i];
        const tr  = document.createElement('tr');
        allCols.forEach(col => {
            const td = document.createElement('td');
            if (col === 'active_medications') {
                const tags = MEDICATION_LIST
                    .filter(m => row[m] && row[m] !== 'No')
                    .map(m => `<span class="med-tag med-${row[m].toLowerCase()}">${m}: ${row[m]}</span>`);
                td.innerHTML = tags.length > 0 ? tags.join('') : '<span style="color:#ccc">None</span>';
            } else {
                const val = row[col];
                td.textContent = val === null ? 'NaN' : val;
                const fi = academicData.features[col];
                if (fi?.type === 'Numeric' && fi.stats && val !== null) {
                    const z = (val - fi.stats.mean) / fi.stats.std;
                    if (z > 1)  td.className = 'val-high';
                    else if (z < -1) td.className = 'val-low';
                }
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
}

// ==================== PAGE 2: CLEAN DATA AUDIT ====================
function initCleanPage() {
    const s = cleaningData.stats;
    document.getElementById('clean-deleted').textContent     = s.deleted_rows.toLocaleString();
    document.getElementById('clean-modified').textContent    = s.modified_rows.toLocaleString();
    document.getElementById('clean-kept').textContent        = s.kept_rows.toLocaleString();
    document.getElementById('clean-dropped-cols').textContent = s.dropped_cols.length;
    document.getElementById('clean-dupes').textContent       = s.deleted_duplicates.toLocaleString();
    document.getElementById('clean-terminal').textContent    = s.deleted_terminal.toLocaleString();

    renderCleanFeatureList();
    renderCleanBrowser();
}

function renderCleanFeatureList(filter = '') {
    const tbody = document.getElementById('clean-feature-tbody');
    tbody.innerHTML = '';

    Object.entries(cleaningData.feature_status).forEach(([col, info]) => {
        if (!col.toLowerCase().includes(filter.toLowerCase())) return;

        const tr = document.createElement('tr');
        if (info.action === 'DROP')   tr.className = 'feat-dropped';
        else if (info.action === 'MODIFY') tr.className = 'feat-modified';

        const badgeClass = info.action === 'DROP' ? 'badge-drop' : info.action === 'MODIFY' ? 'badge-modify' : 'badge-keep';
        tr.innerHTML = `<td><strong>${col}</strong></td><td><span class="${badgeClass}">${info.action}</span></td><td>${info.reason}</td>`;

        tr.addEventListener('click', () => {
            document.querySelectorAll('#clean-feature-tbody tr').forEach(r => r.classList.remove('active-row'));
            tr.classList.add('active-row');
            showCleanFeatureDetail(col, info);
        });
        tbody.appendChild(tr);
    });
}

function showCleanFeatureDetail(col, info) {
    document.getElementById('clean-welcome-message').style.display = 'none';
    document.getElementById('clean-detail-view').style.display = 'block';

    document.getElementById('clean-detail-title').textContent = col;
    const badge = document.getElementById('clean-detail-action-badge');
    badge.textContent = info.action;
    badge.className   = 'badge ' + (info.action === 'DROP' ? 'badge-drop' : info.action === 'MODIFY' ? 'badge-modify' : 'badge-keep');
    document.getElementById('clean-detail-reason').textContent = info.reason;

    // Stats: show deletion reason counts for this column if applicable, or generic feature stats
    const statsBody = document.getElementById('clean-detail-stats-tbody');
    statsBody.innerHTML = '';

    // Find raw feature info
    const rawFeat = academicData.features[col];
    if (rawFeat) {
        [['Missing Count (Raw)', rawFeat.missing_count.toLocaleString()], ['Missing % (Raw)', rawFeat.missing_pct + '%'], ['Unique Values', rawFeat.unique_count.toLocaleString()]].forEach(([k,v]) => {
            statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
        });
        if (rawFeat.type === 'Numeric' && rawFeat.stats?.mean !== undefined) {
            [['Mean', rawFeat.stats.mean], ['Std Dev', rawFeat.stats.std], ['Median', rawFeat.stats.median]].forEach(([k,v]) => {
                if (v !== null) statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
            });
        }
    }

    // Before / after note
    const beforeAfterEl = document.getElementById('clean-detail-before-after');
    if (info.action === 'DROP') {
        beforeAfterEl.innerHTML = `<h4>Cleaning Decision</h4><p>This column is <strong>removed entirely</strong> from the dataset before modeling. No values from this column will be passed to any machine learning algorithm.</p>`;
    } else if (info.action === 'MODIFY') {
        beforeAfterEl.innerHTML = `<h4>Cleaning Decision</h4><p>This column is <strong>transformed</strong> before modeling. The values you see in the raw distribution will be converted according to the strategy above.</p>`;
    } else {
        beforeAfterEl.innerHTML = `<h4>Cleaning Decision</h4><p>This column requires <strong>no modification</strong> and is passed to the model as-is (possibly after scaling).</p>`;
    }

    // Draw chart from CLEANED distribution (not raw)
    const cleanedDist = cleaningData.cleaned_distributions?.[col];
    if (cleanedDist?.labels) {
        const ctx = document.getElementById('clean-distribution-chart').getContext('2d');
        if (cleanChart) cleanChart.destroy();
        const useLog = document.getElementById('clean-toggle-log').checked;

        const color = info.action === 'DROP' ? 'rgba(185,28,28,0.55)'
                    : info.action === 'MODIFY' ? 'rgba(180,130,0,0.65)'
                    : '#0f4c81';

        cleanChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: cleanedDist.labels,
                datasets: [{ data: cleanedDist.values, backgroundColor: color,
                    barPercentage: /^\d/.test(String(cleanedDist.labels[0])) ? 1.0 : 0.8 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                onClick: (e, elements) => {
                    if (elements.length > 0) filterCleanBrowserByValue(col, cleanedDist.labels[elements[0].index]);
                },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { title: (ctx) => {
                        const label = ctx[0].label;
                        const vm = academicData.features[col]?.value_mapping;
                        if (vm?.[label]) return `ID ${label}: ${vm[label]}`;
                        return label;
                    }}}
                },
                scales: {
                    y: { type: useLog ? 'logarithmic' : 'linear', beginAtZero: true },
                    x: { ticks: { maxRotation: 45 } }
                }
            }
        });
    }

    // Filter the bottom table to show rows relevant to this column
    renderCleanBrowser(col);
}

function filterCleanBrowserByValue(col, value) {
    renderCleanBrowser(col, value);
    document.getElementById('clean-browse-title').textContent = `Data Audit Browser — Filtered: ${col} = ${value}`;
}

function renderCleanBrowser(filterCol = null, filterVal = null) {
    if (!cleaningData) return;
    const showDeleted = document.getElementById('show-deleted').checked;
    const limit = parseInt(document.getElementById('clean-limit').value) || 100;

    const thead = document.getElementById('clean-browse-thead');
    const tbody = document.getElementById('clean-browse-tbody');

    if (!filterCol && !filterVal)
        document.getElementById('clean-browse-title').textContent = 'Data Audit Browser — Cleaned Dataset';

    // Use cleaned_sample (post-transformation rows only) unless filtering
    // If show-deleted is on, mix in a peek at raw deleted rows too
    const cleanedSample = cleaningData.cleaned_sample || [];
    const rawSample = cleaningData.sample || [];

    let rows = [];
    if (showDeleted) {
        // Show deleted rows from raw sample first, then cleaned rows
        const deletedRows = rawSample.filter(r => r.__status === 'deleted');
        rows = [...deletedRows, ...cleanedSample.map(r => ({...r, __status: 'kept', __reason: ''})) ];
    } else {
        rows = cleanedSample.map(r => ({...r, __status: 'kept', __reason: ''}));
    }

    if (filterCol && filterVal) {
        rows = rows.filter(r => String(r[filterCol]) === String(filterVal));
    }

    const displayCols = Object.keys(rows[0] || {}).filter(c => !c.startsWith('__') && !MEDICATION_LIST.includes(c));
    if (displayCols.length === 0) { tbody.innerHTML = ''; return; }

    thead.innerHTML = `<tr><th>Status</th><th>Reason</th>${displayCols.map(c => `<th>${c.replace(/_/g,' ')}</th>`).join('')}</tr>`;
    tbody.innerHTML = '';

    let rendered = 0;
    for (const row of rows) {
        if (rendered >= limit) break;

        const tr = document.createElement('tr');
        if (row.__status === 'deleted') tr.className = 'row-deleted';
        else if (row.__status === 'modified') tr.className = 'row-modified';

        const statusLabels = { deleted: 'Deleted', modified: 'Modified', kept: 'Retained' };
        const statusTd = document.createElement('td');
        statusTd.textContent = statusLabels[row.__status] || row.__status;
        statusTd.className = 'reason-cell';
        tr.appendChild(statusTd);

        const reasonTd = document.createElement('td');
        reasonTd.textContent = row.__reason || '';
        reasonTd.className = 'reason-cell';
        tr.appendChild(reasonTd);

        displayCols.forEach(col => {
            const td = document.createElement('td');
            td.textContent = row[col] === null || row[col] === undefined ? 'NaN' : row[col];
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
        rendered++;
    }
}
