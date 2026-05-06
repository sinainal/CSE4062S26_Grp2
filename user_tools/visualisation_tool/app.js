let academicData = null;
let currentChart = null;
let currentFeatureData = null;

const MEDICATION_LIST = ['metformin', 'repaglinide', 'nateglinide', 'chlorpropamide', 'glimepiride', 'acetohexamide', 'glipizide', 'glyburide', 'tolbutamide', 'pioglitazone', 'rosiglitazone', 'acarbose', 'miglitol', 'troglitazone', 'tolazamide', 'examide', 'citoglipton', 'insulin', 'glyburide-metformin', 'glipizide-metformin', 'glimepiride-pioglitazone', 'metformin-rosiglitazone', 'metformin-pioglitazone'];

document.addEventListener('DOMContentLoaded', () => {
    fetch('academic_data.json')
        .then(res => res.json())
        .then(data => {
            academicData = data;
            initDashboard();
        })
        .catch(err => {
            console.error("Error loading JSON:", err);
            document.body.innerHTML = `<div style="padding: 50px; text-align: center; color: red;"><h2>Error Loading Data</h2></div>`;
        });

    document.getElementById('toggle-log-scale').addEventListener('change', () => {
        if (currentFeatureData) renderChart(currentFeatureData);
    });
});

function initDashboard() {
    const overview = academicData.dataset_overview;
    document.getElementById('overview-rows').textContent = overview.total_rows.toLocaleString();
    document.getElementById('overview-cols').textContent = overview.total_cols.toLocaleString();
    document.getElementById('overview-missing').textContent = overview.total_missing_cells.toLocaleString();
    document.getElementById('overview-dupes').textContent = overview.duplicate_rows.toLocaleString();

    renderFeatureList();
    showDrillDown(null, null); // Show all by default

    document.getElementById('feature-search').addEventListener('input', (e) => {
        renderFeatureList(e.target.value);
    });
}

function renderFeatureList(filter = '') {
    const tbody = document.getElementById('feature-tbody');
    tbody.innerHTML = '';
    const features = academicData.features;
    Object.keys(features).forEach(key => {
        if (key.toLowerCase().includes(filter.toLowerCase())) {
            const feat = features[key];
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><strong>${feat.name}</strong></td><td>${feat.missing_pct}%</td><td><span class="action-badge">${feat.cleaning_method}</span></td>`;
            tr.addEventListener('click', () => {
                document.querySelectorAll('#feature-tbody tr').forEach(r => r.classList.remove('active-row'));
                tr.classList.add('active-row');
                currentFeatureData = feat;
                showFeatureDetail(feat);
            });
            tbody.appendChild(tr);
        }
    });
}

function showFeatureDetail(feat) {
    document.getElementById('welcome-message').style.display = 'none';
    document.getElementById('detail-view').style.display = 'block';

    document.getElementById('detail-title').textContent = feat.name;
    document.getElementById('detail-type').textContent = feat.type;
    document.getElementById('detail-description').textContent = feat.description;
    document.getElementById('detail-action-title').textContent = feat.cleaning_method;
    document.getElementById('detail-action-explanation').textContent = feat.cleaning_explanation;

    const statsBody = document.getElementById('detail-stats-tbody');
    statsBody.innerHTML = '';
    const generalStats = [['Missing Count', feat.missing_count.toLocaleString()], ['Missing (%)', feat.missing_pct + '%'], ['Unique Values', feat.unique_count.toLocaleString()]];
    generalStats.forEach(([k, v]) => { statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`; });

    if (feat.type === 'Numeric' && feat.stats && feat.stats.mean !== undefined) {
        const numStats = [['Mean', feat.stats.mean], ['Std Dev', feat.stats.std], ['Median', feat.stats.median], ['Max', feat.stats.max]];
        numStats.forEach(([k, v]) => { if(v !== null) statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`; });
    }

    const logToggle = document.getElementById('toggle-log-scale');
    if (feat.distribution && feat.distribution.values && feat.distribution.values.length > 0) {
        const maxVal = Math.max(...feat.distribution.values);
        const minNonZero = Math.min(...feat.distribution.values.filter(v => v > 0)) || 1;
        logToggle.checked = (maxVal / minNonZero > 50);
    }
    renderChart(feat);
}

function renderChart(feat) {
    const ctx = document.getElementById('distribution-chart').getContext('2d');
    if (currentChart) currentChart.destroy();
    if (!feat.distribution || !feat.distribution.labels) return;

    const isNumeric = feat.type === 'Numeric';
    const useLogScale = document.getElementById('toggle-log-scale').checked;
    
    currentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: feat.distribution.labels,
            datasets: [{
                data: feat.distribution.values,
                backgroundColor: '#0f4c81', 
                barPercentage: isNumeric ? 1.0 : 0.8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const label = feat.distribution.labels[elements[0].index];
                    showDrillDown(feat.name, label);
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (context) => {
                            let label = context[0].label;
                            if (feat.value_mapping && feat.value_mapping[label]) return `ID ${label} : ${feat.value_mapping[label]}`;
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: { type: useLogScale ? 'logarithmic' : 'linear', beginAtZero: true },
                x: { ticks: { maxRotation: 45, minRotation: 0 } }
            }
        }
    });
}

function showDrillDown(featureName, valueLabel) {
    const title = document.getElementById('drill-down-title');
    const thead = document.getElementById('drill-down-thead');
    const tbody = document.getElementById('drill-down-tbody');

    const filtered = featureName 
        ? academicData.raw_sample.filter(row => String(row[featureName]) === String(valueLabel))
        : academicData.raw_sample;
    
    if (!featureName) {
        title.textContent = `Clinical Record Browser (Showing first 100 of ${filtered.length.toLocaleString()} total observations)`;
    } else {
        title.textContent = `Filtered View: ${filtered.length.toLocaleString()} Patients where ${featureName} is ${valueLabel} (Showing first 100 matches)`;
    }

    const baseCols = Object.keys(academicData.raw_sample[0]).filter(c => !MEDICATION_LIST.includes(c));
    const allCols = [...baseCols, 'active_medications'];

    thead.innerHTML = `<tr>${allCols.map(c => `<th>${c.replace(/_/g, ' ')}</th>`).join('')}</tr>`;
    tbody.innerHTML = '';

    // Memory efficient rendering: Only render up to 100 rows in the DOM
    const renderLimit = Math.min(filtered.length, 100);

    for (let i = 0; i < renderLimit; i++) {
        const row = filtered[i];
        const tr = document.createElement('tr');
        
        allCols.forEach(col => {
            const td = document.createElement('td');
            
            if (col === 'active_medications') {
                let activeMeds = [];
                MEDICATION_LIST.forEach(m => {
                    if (row[m] && row[m] !== 'No') {
                        const state = row[m].toLowerCase();
                        activeMeds.push(`<span class="med-tag med-${state}">${m}: ${row[m]}</span>`);
                    }
                });
                td.innerHTML = activeMeds.length > 0 ? activeMeds.join('') : '<span style="color:#ccc">None</span>';
            } else {
                const val = row[col];
                td.textContent = val === null ? 'NaN' : val;

                const featInfo = academicData.features[col];
                if (featInfo && featInfo.type === 'Numeric' && featInfo.stats && val !== null) {
                    const z = (val - featInfo.stats.mean) / featInfo.stats.std;
                    if (z > 1) td.className = 'val-high';
                    else if (z < -1) td.className = 'val-low';
                }
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
}

