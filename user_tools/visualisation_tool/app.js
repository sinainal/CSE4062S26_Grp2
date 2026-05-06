let academicData = null;
let currentChart = null;

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
});

function initDashboard() {
    // 1. Populate Overview
    const overview = academicData.dataset_overview;
    document.getElementById('overview-rows').textContent = overview.total_rows.toLocaleString();
    document.getElementById('overview-cols').textContent = overview.total_cols.toLocaleString();
    document.getElementById('overview-missing').textContent = overview.total_missing_cells.toLocaleString();
    document.getElementById('overview-dupes').textContent = overview.duplicate_rows.toLocaleString();

    // 2. Populate Feature List
    renderFeatureList();

    // Search Box Listener
    document.getElementById('feature-search').addEventListener('input', (e) => {
        renderFeatureList(e.target.value);
    });

    // 3. Populate Raw Data
    renderRawData();
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
            `;
            
            tr.addEventListener('click', () => {
                document.querySelectorAll('#feature-tbody tr').forEach(r => r.classList.remove('active-row'));
                tr.classList.add('active-row');
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
    document.getElementById('detail-note').textContent = feat.academic_note;

    // Render Stats Table
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

    if (feat.type === 'Numeric' && feat.stats) {
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
            if(v !== null) statsBody.innerHTML += `<tr><th>${k}</th><td>${v}</td></tr>`;
        });
    }

    // Render Chart
    renderChart(feat);
}

function renderChart(feat) {
    const ctx = document.getElementById('distribution-chart').getContext('2d');
    if (currentChart) currentChart.destroy();

    const isNumeric = feat.type === 'Numeric';
    const type = isNumeric ? 'bar' : 'bar'; // Both bar, but styled differently

    currentChart = new Chart(ctx, {
        type: type,
        data: {
            labels: feat.distribution.labels,
            datasets: [{
                label: 'Frequency',
                data: feat.distribution.values,
                backgroundColor: '#0f4c81', // Academic blue
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
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#e5e7eb' },
                    ticks: { font: { family: 'Inter' } }
                },
                x: {
                    grid: { display: false },
                    ticks: { 
                        font: { family: 'Inter' },
                        maxRotation: 45,
                        minRotation: 0
                    }
                }
            }
        }
    });
}

function renderRawData() {
    const rawData = academicData.raw_sample;
    if (rawData.length === 0) return;

    const columns = Object.keys(rawData[0]);
    
    // Header
    const thead = document.getElementById('raw-thead');
    let theadHTML = '<tr>';
    columns.forEach(col => {
        theadHTML += `<th>${col}</th>`;
    });
    theadHTML += '</tr>';
    thead.innerHTML = theadHTML;

    // Body
    const tbody = document.getElementById('raw-tbody');
    let tbodyHTML = '';
    rawData.forEach(row => {
        tbodyHTML += '<tr>';
        columns.forEach(col => {
            let val = row[col];
            if (val === null) val = '<span style="color:#b91c1c;">NaN</span>';
            tbodyHTML += `<td>${val}</td>`;
        });
        tbodyHTML += '</tr>';
    });
    tbody.innerHTML = tbodyHTML;
}
