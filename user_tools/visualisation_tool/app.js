let academicData = null;
let cleaningData = null;
let modelReadyData = null;
let baselineModelData = null;
let modelLabData = null;
let clusteringData = null;
let nzvData = null;
let featureSelectionData = null;
let featureSubsetData = null;
let associationRulesData = null;
let currentChart = null;
let cleanChart = null;
let clusterChart = null;
let mlRocChart = null;
let labRocChart = null;
let selectedLabAlgorithm = null;
let selectedClusterMethod = 'kmeans';
let currentFeatureData = null;
let lastFilter = { name: null, label: null };
let icd9Mapping = {};

const MEDICATION_LIST = ['metformin','repaglinide','nateglinide','chlorpropamide','glimepiride','acetohexamide','glipizide','glyburide','tolbutamide','pioglitazone','rosiglitazone','acarbose','miglitol','troglitazone','tolazamide','examide','citoglipton','insulin','glyburide-metformin','glipizide-metformin','glimepiride-pioglitazone','metformin-rosiglitazone','metformin-pioglitazone'];

document.addEventListener('DOMContentLoaded', () => {
    Promise.all([
        fetch('academic_data.json').then(r => r.json()),
        fetch('cleaning_data.json').then(r => r.json()),
        fetch('model_ready_data.json').then(r => r.json()),
        fetch('baseline_model_report.json').then(r => r.json()),
        fetch('model_lab_report.json').then(r => r.json()),
        fetch('clustering_report.json').then(r => r.json()),
        fetch('feature_selection_report.json').then(r => r.json()),
        fetch('feature_subset_report.json').then(r => r.json()),
        fetch('association_rules_report.json').then(r => r.json()),
        fetch('icd9_mapping.json').then(r => r.json()).catch(() => ({})),
        fetch('nzv_report.json').then(r => r.json()).catch(() => ({}))
    ]).then(([data, cleaning, modelReady, baselineModel, modelLab, clustering, featureSelection, featureSubset, associationRules, mapping, nzv]) => {
        academicData = data;
        cleaningData = cleaning;
        modelReadyData = modelReady;
        baselineModelData = baselineModel;
        modelLabData = modelLab;
        clusteringData = clustering;
        featureSelectionData = featureSelection;
        featureSubsetData = featureSubset;
        associationRulesData = associationRules;
        icd9Mapping = mapping;
        nzvData = nzv;
        initRawPage();
        initCleanPage();
        initModelReadyPage();
        initBaselineMLPage();
        initModelLabPage();
        initClusteringPage();
        initAprioriPage();
        // NZV panel is rendered on demand when modal opens
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
    document.getElementById('ready-limit').addEventListener('change', () => renderModelReadyPreview());
    document.getElementById('cluster-method-select').addEventListener('change', () => renderClusteringPage());
    document.getElementById('cluster-k-select').addEventListener('change', () => renderClusteringPage());
    document.getElementById('cluster-color-mode').addEventListener('change', () => renderClusteringPage());
});

// ==================== PAGE SWITCHING ====================
function switchPage(page) {
    document.getElementById('page-raw').style.display   = page === 'raw'   ? '' : 'none';
    document.getElementById('page-clean').style.display = page === 'clean' ? '' : 'none';
    document.getElementById('page-ready').style.display = page === 'ready' ? '' : 'none';
    document.getElementById('page-ml').style.display    = page === 'ml'    ? '' : 'none';
    document.getElementById('page-lab').style.display   = page === 'lab'   ? '' : 'none';
    document.getElementById('page-cluster').style.display = page === 'cluster' ? '' : 'none';
    document.getElementById('page-apriori').style.display = page === 'apriori' ? '' : 'none';
    document.getElementById('tab-raw').classList.toggle('active',   page === 'raw');
    document.getElementById('tab-clean').classList.toggle('active', page === 'clean');
    document.getElementById('tab-ready').classList.toggle('active', page === 'ready');
    document.getElementById('tab-ml').classList.toggle('active',    page === 'ml');
    document.getElementById('tab-lab').classList.toggle('active',   page === 'lab');
    document.getElementById('tab-cluster').classList.toggle('active', page === 'cluster');
    document.getElementById('tab-apriori').classList.toggle('active', page === 'apriori');
    if (page === 'cluster' && clusterChart) {
        setTimeout(() => clusterChart.resize(), 50);
    }
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

// ==================== PAGE 3: MODEL-READY DATA ====================
function initModelReadyPage() {
    if (!modelReadyData) return;
    document.getElementById('ready-rows').textContent = modelReadyData.model_ready_rows.toLocaleString();
    document.getElementById('ready-cols').textContent = modelReadyData.model_ready_columns.toLocaleString();
    document.getElementById('ready-positive').textContent = `${(modelReadyData.positive_class_rate * 100).toFixed(2)}%`;
    document.getElementById('ready-dropped').textContent = modelReadyData.dropped_columns.length.toLocaleString();

    document.getElementById('ready-transformations').innerHTML =
        modelReadyData.transformations.map(item => `<li>${item}</li>`).join('');

    document.getElementById('ready-feature-space').innerHTML = [
        ['Input columns', modelReadyData.input_columns.toLocaleString()],
        ['Numeric columns before encoding', modelReadyData.numeric_columns_before_encoding.length.toLocaleString()],
        ['Categorical columns before encoding', modelReadyData.categorical_columns_before_encoding.length.toLocaleString()],
        ['NZV medication drops', modelReadyData.dropped_nzv_medications.join(', ') || 'None'],
        ['Sample encoded columns', modelReadyData.sample_columns.join(', ')]
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');

    const num = modelReadyData.numeric_pipeline || {};
    document.getElementById('ready-numeric-pipeline').innerHTML = [
        ['Columns', (num.columns || []).join(', ')],
        ['Missing values', num.missing_strategy],
        ['Normalization', num.normalization],
        ['Formula', num.normalization_formula],
        ['Rationale', num.why]
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v || ''}</td></tr>`).join('');

    const cat = modelReadyData.categorical_pipeline || {};
    document.getElementById('ready-categorical-pipeline').innerHTML = [
        ['Columns', (cat.columns || []).join(', ')],
        ['Missing values', cat.missing_strategy],
        ['Encoding', cat.encoding],
        ['Rationale', cat.why]
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v || ''}</td></tr>`).join('');

    const clinical = modelReadyData.clinical_feature_engineering || {};
    document.getElementById('ready-clinical-engineering').innerHTML = Object.entries(clinical)
        .map(([k, v]) => `<tr><th>${k.replace(/_/g, ' ')}</th><td>${v}</td></tr>`).join('');

    const groupRows = Object.entries(modelReadyData.encoded_feature_groups || {})
        .sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `<tr><th>${k}</th><td>${v} encoded columns</td></tr>`);
    document.getElementById('ready-encoded-groups').innerHTML = groupRows.join('');

    renderModelReadyPreview();
}

function renderModelReadyPreview() {
    if (!modelReadyData?.sample_rows?.length) return;
    const limit = parseInt(document.getElementById('ready-limit').value) || 25;
    const rows = modelReadyData.sample_rows.slice(0, limit);
    const cols = Object.keys(rows[0]);
    document.getElementById('ready-thead').innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr>`;
    document.getElementById('ready-tbody').innerHTML = rows.map(row => (
        `<tr>${cols.map(c => `<td>${formatCell(row[c])}</td>`).join('')}</tr>`
    )).join('');
}

function formatCell(value) {
    if (value === null || value === undefined) return 'NaN';
    if (typeof value === 'number') {
        if (Number.isInteger(value)) return value.toString();
        return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
    }
    return value;
}

// ==================== PAGE 4: BASELINE ML TEST ====================
function initBaselineMLPage() {
    if (!baselineModelData) return;
    const best = baselineModelData.best_model || baselineModelData;
    const m = best.metrics || baselineModelData.metrics;
    document.getElementById('ml-model-name').textContent = best.model_name || baselineModelData.model_name;
    document.getElementById('ml-auc').textContent = m.roc_auc.toFixed(3);
    document.getElementById('ml-recall').textContent = m.recall.toFixed(3);
    document.getElementById('ml-f1').textContent = m.f1.toFixed(3);
    document.getElementById('ml-purpose').textContent = baselineModelData.purpose;

    document.getElementById('ml-metrics-tbody').innerHTML = [
        ['Train rows', baselineModelData.split.train_rows.toLocaleString()],
        ['Test rows', baselineModelData.split.test_rows.toLocaleString()],
        ['Accuracy', m.accuracy.toFixed(4)],
        ['Precision', m.precision.toFixed(4)],
        ['Recall', m.recall.toFixed(4)],
        ['F1', m.f1.toFixed(4)],
        ['ROC-AUC', m.roc_auc.toFixed(4)],
        ['Best model', best.model_name || baselineModelData.model_name],
        ['Feature matrix', best.feature_mode || 'model-ready encoded features'],
        ['Test positive rate', `${(baselineModelData.class_balance.test_positive_rate * 100).toFixed(2)}%`]
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');

    renderModelComparison();

    const labels = best.confusion_matrix.labels;
    const matrix = best.confusion_matrix.matrix;
    document.getElementById('ml-confusion-table').innerHTML = `
        <thead><tr><th>Actual \\ Predicted</th><th>${labels[0]}</th><th>${labels[1]}</th></tr></thead>
        <tbody>
            <tr><th>${labels[0]}</th><td>${matrix[0][0].toLocaleString()}</td><td>${matrix[0][1].toLocaleString()}</td></tr>
            <tr><th>${labels[1]}</th><td>${matrix[1][0].toLocaleString()}</td><td>${matrix[1][1].toLocaleString()}</td></tr>
        </tbody>
    `;

    renderCoefficientTable('ml-positive-features', baselineModelData.top_positive_features);
    renderCoefficientTable('ml-negative-features', baselineModelData.top_negative_features);
    renderImportanceTable('ml-rf-features', findModel('Random Forest')?.top_features);
    renderImportanceTable('ml-xgb-features', findModel('XGBoost')?.top_features);
    renderFeatureSelectionSummary();
    renderFeatureSubsetComparison();
    renderMlRocChart();
    renderSignificanceSummary();
}

function renderCoefficientTable(targetId, rows) {
    document.getElementById(targetId).innerHTML = (rows || []).map(row => (
        `<tr><th>${row.feature}</th><td>${row.coefficient.toFixed(4)}</td></tr>`
    )).join('') || '<tr><td>No coefficient data available.</td></tr>';
}

function findModel(name) {
    return (baselineModelData.models || []).find(model => model.model_name === name);
}

function renderModelComparison() {
    const rows = baselineModelData.models || [baselineModelData];
    document.getElementById('ml-comparison-tbody').innerHTML = rows.map(row => {
        const m = row.metrics;
        const bestClass = baselineModelData.best_model?.model_name === row.model_name ? ' class="active-row"' : '';
        return `<tr${bestClass}>
            <td><strong>${row.model_name}</strong></td>
            <td>${m.roc_auc.toFixed(4)}</td>
            <td>${m.accuracy.toFixed(4)}</td>
            <td>${m.precision.toFixed(4)}</td>
            <td>${m.recall.toFixed(4)}</td>
            <td>${m.f1.toFixed(4)}</td>
        </tr>`;
    }).join('');
}

function renderImportanceTable(targetId, rows) {
    document.getElementById(targetId).innerHTML = (rows || []).map(row => (
        `<tr><th>${row.feature}</th><td>${row.importance.toFixed(4)}</td></tr>`
    )).join('') || '<tr><td>Model not available or no importances were produced.</td></tr>';
}

function renderFeatureSelectionSummary() {
    const tbody = document.getElementById('feature-selection-summary');
    if (!tbody || !featureSelectionData?.methods) return;
    const rows = Object.entries(featureSelectionData.methods).map(([method, payload]) => {
        const top = payload.top_features?.[0];
        const topFive = (payload.top_features || []).slice(0, 5).map(item => item.feature).join(', ');
        return `<tr>
            <td><strong>${method.replace(/_/g, ' ')}</strong></td>
            <td>${top ? top.feature : 'n/a'}</td>
            <td>${top ? Number(top.score).toFixed(4) : 'n/a'}</td>
            <td>${topFive || 'n/a'}</td>
        </tr>`;
    }).join('');
    tbody.innerHTML = rows || '<tr><td colspan="4">No feature selection report available.</td></tr>';
}

function renderFeatureSubsetComparison() {
    const tbody = document.getElementById('feature-subset-comparison');
    if (!tbody || !featureSubsetData?.experiments?.length) return;
    tbody.innerHTML = featureSubsetData.experiments.map(exp => {
        const m = exp.metrics;
        return `<tr>
            <td><strong>${exp.feature_set_name}</strong></td>
            <td>${exp.model_name}</td>
            <td>${exp.feature_count}</td>
            <td>${m.roc_auc.toFixed(4)}</td>
            <td>${m.accuracy.toFixed(4)}</td>
            <td>${m.recall.toFixed(4)}</td>
            <td>${m.f1.toFixed(4)}</td>
        </tr>`;
    }).join('');
}

function renderSignificanceSummary() {
    const tbody = document.getElementById('ml-significance-tbody');
    if (!tbody || !baselineModelData?.significance_analysis) return;
    const s = baselineModelData.significance_analysis;
    tbody.innerHTML = [
        ['Best model', baselineModelData.best_model?.model_name || baselineModelData.model_name || 'n/a'],
        ['Closest competitor', baselineModelData.closest_competitor?.model_name || 'n/a'],
        ['Best only correct', s.best_only_correct],
        ['Competitor only correct', s.competitor_only_correct],
        ['Discordant pairs', s.discordant_pairs],
        ['Exact p-value', Number(s.exact_p_value).toFixed(6)],
        ['Significant at 0.05?', s['significant_at_0.05'] ? 'Yes' : 'No'],
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');
}

function renderMlRocChart() {
    const canvas = document.getElementById('ml-roc-chart');
    if (!canvas || !baselineModelData?.roc_curves) return;
    const datasets = Object.entries(baselineModelData.roc_curves).map(([name, curve], idx) => ({
        label: name,
        data: (curve.fpr || []).map((x, i) => ({ x, y: curve.tpr?.[i] ?? 0 })),
        borderColor: ['#0f4c81', '#b91c1c', '#15803d', '#b45309', '#6d28d9'][idx % 5],
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.1,
    }));
    if (mlRocChart) mlRocChart.destroy();
    mlRocChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: {
                x: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'False Positive Rate' } },
                y: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'True Positive Rate' } },
            },
        }
    });
}

function renderLabRocChart(run) {
    const canvas = document.getElementById('lab-roc-chart');
    if (!canvas || !run?.roc_curve) return;
    if (labRocChart) labRocChart.destroy();
    labRocChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            datasets: [{
                label: `${run.model_name} ROC`,
                data: (run.roc_curve.fpr || []).map((x, i) => ({ x, y: run.roc_curve.tpr?.[i] ?? 0 })),
                borderColor: '#0f4c81',
                backgroundColor: 'transparent',
                pointRadius: 0,
                borderWidth: 2,
                tension: 0.1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: true, position: 'bottom' } },
            scales: {
                x: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'False Positive Rate' } },
                y: { type: 'linear', min: 0, max: 1, title: { display: true, text: 'True Positive Rate' } },
            },
        }
    });
}

// ==================== PAGE 5: LIVE MODEL LAB ====================
function initModelLabPage() {
    if (!modelLabData?.algorithms?.length) return;
    selectedLabAlgorithm = modelLabData.best_overall?.model_name || modelLabData.algorithms[0].name;

    const sample = modelLabData.sample || {};
    document.getElementById('lab-sample-note').textContent =
        `${modelLabData.sample_policy} Train: ${(sample.train_rows || 0).toLocaleString()} / Test: ${(sample.test_rows || 0).toLocaleString()}; full split is ${(sample.full_train_rows || 0).toLocaleString()} / ${(sample.full_test_rows || 0).toLocaleString()}.`;

    renderLabAlgorithmButtons();
    renderLabComparison();
    selectLabAlgorithm(selectedLabAlgorithm);
}

function renderLabAlgorithmButtons() {
    const wrap = document.getElementById('lab-algorithm-buttons');
    wrap.innerHTML = '';
    modelLabData.algorithms.forEach(algorithm => {
        const btn = document.createElement('button');
        btn.className = `algorithm-btn${algorithm.name === selectedLabAlgorithm ? ' active' : ''}`;
        btn.textContent = algorithm.name;
        btn.disabled = !algorithm.runs?.length;
        btn.addEventListener('click', () => selectLabAlgorithm(algorithm.name));
        wrap.appendChild(btn);
    });
}

function selectLabAlgorithm(name) {
    selectedLabAlgorithm = name;
    renderLabAlgorithmButtons();
    const algorithm = getLabAlgorithm(name);
    renderLabControls(algorithm);
    renderSelectedLabRun();
}

function getLabAlgorithm(name) {
    return (modelLabData.algorithms || []).find(algorithm => algorithm.name === name);
}

function renderLabControls(algorithm) {
    const wrap = document.getElementById('lab-controls');
    wrap.innerHTML = '';
    if (!algorithm?.runs?.length) {
        wrap.innerHTML = `<p class="inline-note">${algorithm?.unavailable_reason || 'This algorithm did not produce runs.'}</p>`;
        return;
    }

    (algorithm.controls || []).forEach(control => {
        const label = document.createElement('label');
        label.className = 'control-field';
        const select = document.createElement('select');
        select.id = `lab-control-${control.name}`;
        select.dataset.param = control.name;
        control.values.forEach(value => {
            const option = document.createElement('option');
            option.value = String(value);
            option.textContent = String(value);
            select.appendChild(option);
        });
        if (algorithm.best?.params?.[control.name] !== undefined) {
            select.value = String(algorithm.best.params[control.name]);
        }
        select.addEventListener('change', renderSelectedLabRun);
        label.innerHTML = `<span>${control.label}</span>`;
        label.appendChild(select);
        wrap.appendChild(label);
    });
}

function findSelectedLabRun(algorithm) {
    if (!algorithm?.runs?.length) return null;
    const selected = {};
    (algorithm.controls || []).forEach(control => {
        const element = document.getElementById(`lab-control-${control.name}`);
        if (element) selected[control.name] = element.value;
    });
    return algorithm.runs.find(run => {
        return Object.entries(selected).every(([key, value]) => String(run.params?.[key]) === String(value));
    }) || algorithm.best || algorithm.runs[0];
}

function renderSelectedLabRun() {
    const algorithm = getLabAlgorithm(selectedLabAlgorithm);
    const run = findSelectedLabRun(algorithm);
    if (!run) return;
    const metrics = run.metrics;
    document.getElementById('lab-model-name').textContent = run.model_name;
    document.getElementById('lab-auc').textContent = metrics.roc_auc.toFixed(3);
    document.getElementById('lab-recall').textContent = metrics.recall.toFixed(3);
    document.getElementById('lab-f1').textContent = metrics.f1.toFixed(3);

    document.getElementById('lab-metrics-tbody').innerHTML = [
        ['Settings', formatParams(run.params)],
        ['Accuracy', metrics.accuracy.toFixed(4)],
        ['Precision', metrics.precision.toFixed(4)],
        ['Recall', metrics.recall.toFixed(4)],
        ['F1', metrics.f1.toFixed(4)],
        ['ROC-AUC', metrics.roc_auc.toFixed(4)],
        ['Feature matrix', run.feature_mode || 'sampled model-ready encoded features']
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');

    const labels = run.confusion_matrix.labels;
    const matrix = run.confusion_matrix.matrix;
    document.getElementById('lab-confusion-table').innerHTML = `
        <thead><tr><th>Actual \\ Predicted</th><th>${labels[0]}</th><th>${labels[1]}</th></tr></thead>
        <tbody>
            <tr><th>${labels[0]}</th><td>${matrix[0][0].toLocaleString()}</td><td>${matrix[0][1].toLocaleString()}</td></tr>
            <tr><th>${labels[1]}</th><td>${matrix[1][0].toLocaleString()}</td><td>${matrix[1][1].toLocaleString()}</td></tr>
        </tbody>
    `;

    const featureRows = run.top_features || [];
    document.getElementById('lab-feature-note').textContent =
        featureRows.length ? 'Tree-based models expose impurity feature importances for the current run.' : 'This model type does not expose a direct feature-importance table in the current lab configuration.';
    renderImportanceTable('lab-feature-table', featureRows);
    renderLabRocChart(run);
}

function renderLabComparison() {
    const rows = (modelLabData.algorithms || []).map(algorithm => ({ algorithm, run: algorithm.best }));
    document.getElementById('lab-comparison-tbody').innerHTML = rows.map(({ algorithm, run }) => {
        if (!run) {
            return `<tr><td><strong>${algorithm.name}</strong></td><td colspan="6">${algorithm.unavailable_reason || 'No run available.'}</td></tr>`;
        }
        const metrics = run.metrics;
        const bestClass = modelLabData.best_overall?.model_name === run.model_name &&
            formatParams(modelLabData.best_overall?.params) === formatParams(run.params) ? ' class="active-row"' : '';
        return `<tr${bestClass}>
            <td><strong>${algorithm.name}</strong></td>
            <td>${formatParams(run.params)}</td>
            <td>${metrics.roc_auc.toFixed(4)}</td>
            <td>${metrics.accuracy.toFixed(4)}</td>
            <td>${metrics.precision.toFixed(4)}</td>
            <td>${metrics.recall.toFixed(4)}</td>
            <td>${metrics.f1.toFixed(4)}</td>
        </tr>`;
    }).join('');
}

function formatParams(params) {
    const entries = Object.entries(params || {});
    if (!entries.length) return 'default';
    return entries.map(([key, value]) => `${key}=${value}`).join(', ');
}

// ==================== PAGE 6: CLUSTERING LAB ====================
function initClusteringPage() {
    if (!clusteringData?.points?.length) return;
    const methodSelect = document.getElementById('cluster-method-select');
    methodSelect.innerHTML = Object.keys(clusteringData.methods || {})
        .map(key => `<option value="${key}">${clusteringData.methods[key].label}</option>`).join('');
    methodSelect.value = 'kmeans';
    selectedClusterMethod = 'kmeans';
    populateClusterParamSelect();
    renderClusterMethodComparison();
    renderClusteringPage();
}

function populateClusterParamSelect() {
    const method = clusteringData.methods?.[selectedClusterMethod];
    const select = document.getElementById('cluster-k-select');
    const label = document.getElementById('cluster-param-label');
    if (!method || !select || !label) return;

    label.textContent = method.parameter_name === 'eps/min_samples' ? 'DBSCAN config' : 'Number of clusters';
    const options = selectedClusterMethod === 'dbscan'
        ? (method.runs || []).map(run => `${run.eps}/${run.min_samples}`)
        : (method.parameter_values || Object.keys(method.runs || {}));
    select.innerHTML = options.map(value => `<option value="${value}">${value}</option>`).join('');

    const bestValue = method.best?.eps !== undefined
        ? `${method.best.eps}/${method.best.min_samples}`
        : (Object.keys(method.runs || {}).find(k => method.runs[k]?.silhouette === method.best?.silhouette) || options[Math.min(2, options.length - 1)]);
    if (bestValue && Array.from(select.options).some(opt => opt.value === String(bestValue))) {
        select.value = String(bestValue);
    } else if (options.includes('4')) {
        select.value = '4';
    } else if (options.length) {
        select.value = options[0];
    }
}

function getSelectedClusterRun() {
    const method = clusteringData.methods?.[selectedClusterMethod];
    if (!method) return null;
    const param = document.getElementById('cluster-k-select').value;
    if (selectedClusterMethod === 'dbscan') {
        const run = (method.runs || []).find(r => `${r.eps}/${r.min_samples}` === String(param));
        return { method, param, run: run || method.best };
    }
    return { method, param, run: method.runs?.[String(param)] || method.best };
}

function renderClusteringPage() {
    if (!clusteringData?.points?.length) return;
    const methodKey = document.getElementById('cluster-method-select').value || 'kmeans';
    if (methodKey !== selectedClusterMethod) {
        selectedClusterMethod = methodKey;
        populateClusterParamSelect();
    }
    const selection = getSelectedClusterRun();
    if (!selection?.run) return;
    const clustering = selection.run;

    document.getElementById('cluster-sample-rows').textContent = clusteringData.method.sample_rows.toLocaleString();
    document.getElementById('cluster-variance').textContent = `${(clusteringData.method.total_explained_variance * 100).toFixed(1)}%`;
    document.getElementById('cluster-k-value').textContent = selectedClusterMethod === 'dbscan' ? selection.param : selection.param;
    document.getElementById('cluster-silhouette').textContent = clustering.silhouette !== null && clustering.silhouette !== undefined ? clustering.silhouette.toFixed(3) : 'n/a';

    renderClusterSummary(clustering);
    renderClusterChart(selection);
    renderClusterMethodComparison();
}

function renderClusterMethodComparison() {
    const tbody = document.getElementById('cluster-method-comparison');
    if (!tbody || !clusteringData?.methods) return;
    const rows = Object.entries(clusteringData.methods).map(([key, method]) => {
        const best = method.best;
        const bestLabel = key === 'dbscan' && best
            ? `eps=${best.eps}, min_samples=${best.min_samples}`
            : `k=${Object.keys(method.runs || {}).find(k => method.runs[k] === best) || 'n/a'}`;
        return `<tr>
            <th>${method.label}</th>
            <td>${bestLabel}</td>
            <td>${best?.silhouette !== null && best?.silhouette !== undefined ? Number(best.silhouette).toFixed(3) : 'n/a'}</td>
            <td>${best?.cluster_count ?? 'n/a'}</td>
            <td>${best?.noise_count ?? 0}</td>
        </tr>`;
    }).join('');
    tbody.innerHTML = rows;
}

function renderClusterSummary(clustering) {
    document.getElementById('cluster-summary-tbody').innerHTML = Object.keys(clustering.sizes).map(label => {
        const size = clustering.sizes[label];
        const rate = (clustering.readmission_rates[label] * 100).toFixed(2);
        return `<tr><th>Cluster ${label}</th><td>${size.toLocaleString()} rows | ${rate}% &lt;30 readmission</td></tr>`;
    }).join('');
}

function renderClusterChart(selection) {
    const clustering = selection.run;
    const mode = document.getElementById('cluster-color-mode').value;
    const groups = {};
    clusteringData.points.forEach((point, idx) => {
        const clusterLabel = clustering.labels[idx];
        let group = `Cluster ${clusterLabel}`;
        if (mode === 'readmitted') group = point.readmitted ? 'Readmitted <30' : 'Not <30';
        if (mode === 'race') group = point.race || 'Unknown';
        if (mode === 'diag_1_group') group = point.diag_1_group || 'Unknown';
        if (!groups[group]) groups[group] = [];
        groups[group].push({
            x: point.x,
            y: point.y,
            meta: { ...point, cluster: clusterLabel }
        });
    });

    const palette = ['#0f4c81', '#b91c1c', '#15803d', '#b45309', '#6d28d9', '#0f766e', '#be123c', '#334155', '#ca8a04', '#0369a1'];
    const datasets = Object.entries(groups).map(([label, points], idx) => ({
        label,
        data: points,
        backgroundColor: palette[idx % palette.length],
        borderColor: palette[idx % palette.length],
        pointRadius: 3,
        pointHoverRadius: 6
    }));

    if (clusterChart) clusterChart.destroy();
    const ctx = document.getElementById('cluster-chart').getContext('2d');
    clusterChart = new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        title: items => items[0]?.dataset?.label || '',
                        label: item => {
                            const meta = item.raw.meta;
                            return [
                                `PCA: (${item.raw.x.toFixed(2)}, ${item.raw.y.toFixed(2)})`,
                                `Cluster: ${meta.cluster}`,
                                `Readmitted <30: ${meta.readmitted ? 'Yes' : 'No'}`,
                                `Diag: ${meta.diag_1_group}`,
                                `Race: ${meta.race}`,
                                `Age: ${meta.age}`,
                                `Hospital stay: ${meta.time_in_hospital} days`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'PCA component 1' } },
                y: { title: { display: true, text: 'PCA component 2' } }
            }
        }
    });
}

function initAprioriPage() {
    if (!associationRulesData) return;
    document.getElementById('apriori-transactions').textContent = associationRulesData.total_transactions.toLocaleString();
    document.getElementById('apriori-itemsets').textContent = (associationRulesData.frequent_itemsets || []).length.toLocaleString();
    document.getElementById('apriori-rules').textContent = (associationRulesData.rules || []).length.toLocaleString();
    document.getElementById('apriori-support').textContent = Number(associationRulesData.min_support).toFixed(2);
    document.getElementById('apriori-note').textContent =
        `Transactions are built from ${associationRulesData.columns_used?.length || 0} interpretable clinical fields and mined with a compact Apriori-style search (support >= ${Number(associationRulesData.min_support).toFixed(2)}, confidence >= ${Number(associationRulesData.min_confidence).toFixed(2)}).`;

    document.getElementById('apriori-method-tbody').innerHTML = [
        ['Columns used', (associationRulesData.columns_used || []).join(', ')],
        ['Sample rows', associationRulesData.sample_rows.toLocaleString()],
        ['Max itemset length', associationRulesData.max_length],
        ['Min confidence', Number(associationRulesData.min_confidence).toFixed(2)],
    ].map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join('');

    document.getElementById('apriori-itemsets-tbody').innerHTML = (associationRulesData.frequent_itemsets || []).slice(0, 12).map(item => (
        `<tr><td>${item.items.join(' + ')}</td><td>${Number(item.support).toFixed(4)}</td><td>${item.count.toLocaleString()}</td></tr>`
    )).join('');

    document.getElementById('apriori-rules-tbody').innerHTML = (associationRulesData.rules || []).slice(0, 12).map(rule => (
        `<tr><td>${rule.antecedent.join(' + ')}</td><td>${rule.consequent.join(' + ')}</td><td>${Number(rule.support).toFixed(4)}</td><td>${Number(rule.confidence).toFixed(4)}</td><td>${rule.lift !== null ? Number(rule.lift).toFixed(4) : 'n/a'}</td></tr>`
    )).join('');
}

// initNZVPanel removed — code generation moved into openNZVModal()

function copyCode() {
    const text = document.getElementById('cleaning-code-display').textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.querySelector('.copy-btn');
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
}

// ==================== NZV MODAL ====================
let fullNZVData = null;
let currentNZVFilter = 'all';

// Load full_nzv_report.json alongside other data
fetch('full_nzv_report.json').then(r => r.json()).then(data => {
    fullNZVData = data;
}).catch(() => {});

function openNZVModal() {
    document.getElementById('nzv-modal').classList.add('open');
    // Render full NZV table from full_nzv_report data
    if (fullNZVData) renderFullNZVTable('all');
    // Generate code from nzvData (medication-only NZV report)
    const src = nzvData || fullNZVData;
    if (src) {
        const dropped = Object.entries(src).filter(([,m]) => m.drop).map(([c]) => `'${c}'`);
        const kept    = Object.entries(src).filter(([,m]) => !m.drop).map(([c]) => `'${c}'`);
        const code = `# Near-Zero Variance (NZV) Cleaning Pipeline
# Ref: Kuhn & Johnson (2013); Pedregosa et al. (2011)

import pandas as pd
import numpy as np

FR_THRESHOLD  = 20.0    # Frequency Ratio threshold
UP_THRESHOLD  = 10.0    # Uniqueness Percentage threshold (%)
VAR_THRESHOLD = 0.0475  # p0*(1-p0) where p0 = 0.95

def compute_nzv(series, numeric=False):
    vc = series.dropna().value_counts()
    n  = len(series.dropna())
    if n == 0: return True
    fr  = vc.iloc[0] / (vc.iloc[1] if len(vc) > 1 else 1)
    up  = (len(vc) / n) * 100
    p   = vc.iloc[0] / n
    var = p * (1 - p)
    is_nzv = (fr > FR_THRESHOLD) and (up < UP_THRESHOLD)
    below  = (not numeric) and (var < VAR_THRESHOLD)
    return is_nzv or below

df = pd.read_csv('diabetic_data.csv', na_values=['?'])

# 1. Row filtering (Strack et al., 2014)
df = df.sort_values('encounter_id')
df = df.drop_duplicates(subset=['patient_nbr'], keep='first')
df = df[~df['discharge_disposition_id'].isin([11,13,14,19,20,21])]
df = df[df['gender'] != 'Unknown/Invalid']

# 2. NZV column removal (applied to categorical medication columns)
DROP_COLS = [
${dropped.map(c => `    ${c},`).join('\n')}
]
df = df.drop(columns=DROP_COLS)
# Kept medication cols: ${kept.join(', ')}

# 3. Missing value imputation
df['race']              = df['race'].fillna('Unknown')
df['medical_specialty'] = df['medical_specialty'].fillna('Missing')
for col in ['diag_1', 'diag_2', 'diag_3']:
    df[col] = df[col].fillna('Unknown')

print(f"Final shape: {df.shape}")
print(f"Readmission rate (<30d): {(df['readmitted']=='<30').mean():.4f}")`;
        const pre = document.getElementById('cleaning-code-display');
        if (pre) pre.textContent = code;
    }
}


function closeNZVModal(event) {
    if (!event || event.target === document.getElementById('nzv-modal') || event.currentTarget.classList.contains('modal-close-btn')) {
        document.getElementById('nzv-modal').classList.remove('open');
    }
}

function filterNZVModal(filter, btn) {
    currentNZVFilter = filter;
    document.querySelectorAll('.modal-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderFullNZVTable(filter);
}

function renderFullNZVTable(filter) {
    if (!fullNZVData) return;
    const tbody = document.getElementById('full-nzv-tbody');
    tbody.innerHTML = '';
    let count = 0;

    Object.entries(fullNZVData).forEach(([col, m]) => {
        if (filter === 'drop' && !m.drop) return;
        if (filter === 'keep' && m.drop) return;

        const tr = document.createElement('tr');
        if (m.drop) tr.className = 'feat-dropped';

        const frStr = m.fr >= 1e9 ? '∞' : m.fr.toFixed(1);
        const typeStr = m.is_numeric ? 'Numeric' : 'Categorical';
        const nzvBadge = m.is_nzv ? '<span class="badge-nzv-yes">Yes</span>' : '<span class="badge-nzv-no">No</span>';
        const varBadge = m.below_var_thresh ? '<span class="badge-nzv-yes">Yes</span>' : '<span class="badge-nzv-no">No</span>';
        const decBadge = m.drop ? '<span class="badge-drop">DROP</span>' : '<span class="badge-keep">KEEP</span>';

        tr.innerHTML = `
            <td><strong>${col}</strong></td>
            <td>${typeStr}</td>
            <td>${frStr}</td>
            <td>${m.up.toFixed(4)}</td>
            <td>${m.variance.toFixed(6)}</td>
            <td>${nzvBadge}</td>
            <td>${varBadge}</td>
            <td>${decBadge}</td>`;
        tbody.appendChild(tr);
        count++;
    });

    const dropped = Object.values(fullNZVData).filter(m => m.drop).length;
    const kept    = Object.values(fullNZVData).length - dropped;
    document.getElementById('modal-count').textContent =
        `Showing ${count} columns | ${dropped} DROP / ${kept} KEEP`;
}
