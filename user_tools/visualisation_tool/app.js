let dataSummary = null;
let currentFeature = null;
let myChart = null;
let currentChartType = 'bar';

// Load Data
fetch('data_summary.json')
    .then(response => response.json())
    .then(data => {
        dataSummary = data;
        initApp();
    })
    .catch(err => console.error("Error loading data:", err));

function initApp() {
    document.getElementById('total-rows').textContent = `Rows: ${dataSummary.total_rows.toLocaleString()}`;
    document.getElementById('total-cols').textContent = `Cols: ${dataSummary.total_columns}`;
    
    renderFeatureList();
    
    document.getElementById('search-features').addEventListener('input', (e) => {
        renderFeatureList(e.target.value);
    });
}

function renderFeatureList(filter = "") {
    const list = document.getElementById('feature-list');
    list.innerHTML = "";
    
    Object.keys(dataSummary.columns).sort().forEach(key => {
        if (key.toLowerCase().includes(filter.toLowerCase())) {
            const li = document.createElement('li');
            const type = dataSummary.columns[key].type;
            li.innerHTML = `
                <span>${key}</span>
                <span class="type-indicator" style="background: ${type === 'numerical' ? 'rgba(79, 70, 229, 0.2)' : 'rgba(16, 185, 129, 0.2)'}">
                    ${type === 'numerical' ? 'NUM' : 'CAT'}
                </span>
            `;
            li.onclick = () => selectFeature(key);
            if (currentFeature === key) li.classList.add('active');
            list.appendChild(li);
        }
    });
}

function selectFeature(name) {
    currentFeature = name;
    const feat = dataSummary.columns[name];
    
    // Update UI
    document.getElementById('welcome-screen').style.display = 'none';
    document.getElementById('analysis-view').style.display = 'grid';
    document.getElementById('current-feature-name').textContent = name;
    document.getElementById('feature-type-tag').textContent = feat.type;
    document.getElementById('stat-missing').textContent = `${feat.missing_pct}%`;
    document.getElementById('stat-unique').textContent = feat.unique_count;
    
    const analysisView = document.getElementById('analysis-view');
    if (feat.type === 'numerical') {
        analysisView.classList.add('is-numerical');
        document.getElementById('stat-mean').textContent = feat.mean.toFixed(2);
    } else {
        analysisView.classList.remove('is-numerical');
    }

    renderChart();
    generateInsight(name, feat);
    renderFeatureList(document.getElementById('search-features').value);
}

function changeChartType(type) {
    currentChartType = type;
    
    // Update buttons
    const buttons = document.querySelectorAll('.chart-controls .btn');
    buttons.forEach(btn => {
        if (btn.textContent.toLowerCase() === type) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    
    renderChart();
}

function renderChart() {
    const feat = dataSummary.columns[currentFeature];
    const ctx = document.getElementById('mainChart').getContext('2d');
    
    if (myChart) myChart.destroy();
    
    const colors = [
        '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
        '#ec4899', '#06b6d4', '#f97316', '#64748b', '#14b8a6'
    ];

    myChart = new Chart(ctx, {
        type: currentChartType,
        data: {
            labels: feat.distribution.labels,
            datasets: [{
                label: 'Frequency',
                data: feat.distribution.values,
                backgroundColor: currentChartType === 'pie' ? colors : colors[0],
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: currentChartType === 'pie',
                    labels: { color: '#94a3b8' }
                }
            },
            scales: currentChartType === 'bar' ? {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            } : {}
        }
    });
}

function generateInsight(name, feat) {
    const insightBox = document.getElementById('preprocessing-insight');
    let text = "";

    if (feat.missing_pct > 30) {
        text = `High missing rate (${feat.missing_pct}%). This feature might be better removed unless it's crucial.`;
    } else if (feat.missing_pct > 0) {
        text = `Contains missing values (${feat.missing_pct}%). Consider imputation using ${feat.type === 'numerical' ? 'mean/median' : 'mode'} or a 'Missing' category.`;
    }

    if (feat.unique_count === 1) {
        text += " Constant value detected. Recommend dropping this feature.";
    }

    if (feat.type === 'categorical') {
        if (feat.unique_count > 10) {
            text += ` High cardinality (${feat.unique_count} classes). Consider grouping rare categories or using Target Encoding.`;
        } else {
            text += " Standard categorical feature. Suitable for One-Hot or Label Encoding.";
        }
    }

    if (name === 'diag_1' || name === 'diag_2' || name === 'diag_3') {
        text = "Medical diagnosis codes. Recommend grouping these into broader categories (e.g., Circulatory, Respiratory) as per ICD-9 standards.";
    }

    if (name === 'weight' || name === 'payer_code' || name === 'medical_specialty') {
        text = "This feature is known to have high missingness in this dataset. Handle with care or drop if quality is too low.";
    }

    insightBox.textContent = text || "Looks standard. Normal preprocessing applies.";
}
