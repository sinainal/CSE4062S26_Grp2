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

            tr.innerHTML = `
                <td><strong>${feat.name}</strong></td>
                <td>${feat.type}</td>
                <td class="${missingClass}">${feat.missing_pct}%</td>
                <td><span class="action-badge">${feat.cleaning_method}</span></td>
            `;
            
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
    
    const generalStats = [
        ['Missing Count', feat.missing_count.toLocaleString()],
        ['Missing (%)', feat.missing_pct + '%'],
        ['Unique Values', feat.unique_count.toLocaleString()]
    ];

    generalStats.forEach(([k, v]) => {
        statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
    });

    if (feat.type === 'Numeric' && feat.stats && feat.stats.mean !== undefined) {
        const numStats = [
            ['Mean', feat.stats.mean],
            ['Std Dev', feat.stats.std],
            ['Minimum', feat.stats.min],
            ['25th Pct', feat.stats.q25],
            ['Median', feat.stats.median],
            ['75th Pct', feat.stats.q75],
            ['Maximum', feat.stats.max]
        ];
        numStats.forEach(([k, v]) => {
            if(v !== null && v !== undefined) {
                statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
            }
        });
    }

    const logToggle = document.getElementById('toggle-log-scale');
    if (feat.distribution && feat.distribution.values && feat.distribution.values.length > 0) {
        const maxVal = Math.max(...feat.distribution.values);
        const minNonZero = Math.min(...feat.distribution.values.filter(v => v > 0)) || 1;
        if (maxVal / minNonZero > 50) {
            logToggle.checked = true;
        } else {
            logToggle.checked = false;
        }
    }

    renderChart(feat);
}

function renderChart(feat) {
    const ctx = document.getElementById('distribution-chart').getContext('2d');
    if (currentChart) currentChart.destroy();

    if (!feat.distribution || !feat.distribution.labels || feat.distribution.labels.length === 0) {
        currentChart = new Chart(ctx, {
            type: 'bar',
            data: { labels: ['No Data'], datasets: [{ data: [0] }] },
            options: { plugins: { title: { display: true, text: 'No valid data available (All NaN)' } } }
        });
        return;
    }

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
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            let label = context[0].label;
                            // Check if there is a mapping for this raw value
                            if (feat.value_mapping && feat.value_mapping[label]) {
                                return `ID ${label} : ${feat.value_mapping[label]}`;
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    type: useLogScale ? 'logarithmic' : 'linear',
                    beginAtZero: true,
                    grid: { color: '#e5e7eb' },
                    ticks: { font: { family: 'Inter' } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter' }, maxRotation: 45, minRotation: 0 }
                }
            }
        }
    });
}
