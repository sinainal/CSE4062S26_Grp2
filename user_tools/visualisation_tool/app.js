let academicData = null;
let currentChart = null;
let currentFeatureData = null;

document.addEventListener('DOMContentLoaded', () => {
    fetch('academic_data.json')
        .then(res => res.json())
        .then(data => {
            academicData = data;
            initDashboard();
        })
        .catch(err => {
            console.error("Error loading JSON:", err);
            document.body.innerHTML = `<div style="padding: 50px; text-align: center; color: red;">
                <h2>Error Loading Data</h2>
                <p>Could not load academic_data.json. Are you running this through a local server?</p>
            </div>`;
        });

    document.getElementById('toggle-log-scale').addEventListener('change', () => {
        if (currentFeatureData) {
            renderChart(currentFeatureData);
        }
    });
});

function initDashboard() {
    const overview = academicData.dataset_overview;
    document.getElementById('overview-rows').textContent = overview.total_rows.toLocaleString();
    document.getElementById('overview-cols').textContent = overview.total_cols.toLocaleString();
    document.getElementById('overview-missing').textContent = overview.total_missing_cells.toLocaleString();
    document.getElementById('overview-dupes').textContent = overview.duplicate_rows.toLocaleString();

    renderFeatureList();

    document.getElementById('feature-search').addEventListener('input', (e) => {
        renderFeatureList(e.target.value);
    });

    initCaseExplorer();
}

function initCaseExplorer() {
    const dropdown = document.getElementById('case-dropdown');
    const cases = academicData.raw_sample;
    
    cases.forEach((record, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = `Encounter: ${record.encounter_id} (Patient: ${record.patient_nbr})`;
        dropdown.appendChild(option);
    });

    dropdown.addEventListener('change', (e) => {
        const index = e.target.value;
        if (index === "") {
            document.getElementById('case-detail-box').style.display = 'none';
        } else {
            renderCaseDetail(cases[index]);
        }
    });
}

function renderCaseDetail(record) {
    const box = document.getElementById('case-detail-box');
    box.innerHTML = '';
    box.style.display = 'grid';

    Object.keys(record).forEach(key => {
        const item = document.createElement('div');
        item.className = 'case-item';
        if (['readmitted', 'diag_1', 'time_in_hospital'].includes(key)) {
            item.classList.add('highlight');
        }
        let val = record[key];
        if (val === null) val = 'NaN';
        item.innerHTML = `<span class="label">${key.replace(/_/g, ' ')}</span><span class="value">${val}</span>`;
        box.appendChild(item);
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
            const missingClass = feat.missing_pct > 10 ? 'missing-warning' : '';
            tr.innerHTML = `<td><strong>${feat.name}</strong></td><td>${feat.type}</td><td class="${missingClass}">${feat.missing_pct}%</td><td><span class="action-badge">${feat.cleaning_method}</span></td>`;
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
    document.getElementById('drill-down-container').style.display = 'none'; // Reset drill-down

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
        const numStats = [['Mean', feat.stats.mean], ['Std Dev', feat.stats.std], ['Minimum', feat.stats.min], ['25th Pct', feat.stats.q25], ['Median', feat.stats.median], ['75th Pct', feat.stats.q75], ['Maximum', feat.stats.max]];
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
                label: 'Frequency',
                data: feat.distribution.values,
                backgroundColor: '#0f4c81', 
                borderColor: '#0f4c81',
                borderWidth: 1,
                barPercentage: isNumeric ? 1.0 : 0.8,
                categoryPercentage: isNumeric ? 1.0 : 0.8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const label = feat.distribution.labels[index];
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
    const container = document.getElementById('drill-down-container');
    const title = document.getElementById('drill-down-title');
    const thead = document.getElementById('drill-down-thead');
    const tbody = document.getElementById('drill-down-tbody');

    container.style.display = 'block';
    title.textContent = `Drill-Down: Patients where ${featureName} is ${valueLabel} (Showing first matches in sample)`;

    // Filter raw sample
    const filtered = academicData.raw_sample.filter(row => String(row[featureName]) === valueLabel);
    
    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="50">No patients matching this criteria in the current sample.</td></tr>';
        return;
    }

    // Header: Show subset of interesting columns to keep it readable
    const colsToShow = ['encounter_id', 'patient_nbr', 'race', 'gender', 'age', 'time_in_hospital', 'num_lab_procedures', 'num_medications', 'readmitted'];
    thead.innerHTML = `<tr>${colsToShow.map(c => `<th>${c}</th>`).join('')}</tr>`;

    tbody.innerHTML = '';
    filtered.forEach(row => {
        const tr = document.createElement('tr');
        colsToShow.forEach(col => {
            const td = document.createElement('td');
            const val = row[col];
            td.textContent = val === null ? 'NaN' : val;

            // Apply STD-based coloring for numerical columns
            const featInfo = academicData.features[col];
            if (featInfo && featInfo.type === 'Numeric' && featInfo.stats && val !== null) {
                const mean = featInfo.stats.mean;
                const std = featInfo.stats.std;
                if (std > 0) {
                    const z = (val - mean) / std;
                    if (z > 1) td.className = 'val-high';
                    else if (z < -1) td.className = 'val-low';
                    else td.className = 'val-normal';
                }
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    
    // Scroll to the drill-down section
    container.scrollIntoView({ behavior: 'smooth' });
}
