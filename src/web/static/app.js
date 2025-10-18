// TradeScout Web Interface - JavaScript

let currentResults = null;

// Load screeners on page load
document.addEventListener('DOMContentLoaded', () => {
    loadScreeners();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('close-results').addEventListener('click', closeResults);
    document.getElementById('export-csv').addEventListener('click', exportToCSV);
}

// Fetch and display available screeners
async function loadScreeners() {
    const grid = document.getElementById('screeners-grid');

    try {
        const response = await fetch('/api/screeners');
        if (!response.ok) throw new Error('Failed to load screeners');

        const screeners = await response.json();

        grid.innerHTML = '';

        if (screeners.length === 0) {
            grid.innerHTML = '<div class="loading">No screeners available</div>';
            return;
        }

        screeners.forEach(screener => {
            if (!screener.enabled) return; // Skip disabled screeners

            const card = createScreenerCard(screener);
            grid.appendChild(card);
        });
    } catch (error) {
        console.error('Error loading screeners:', error);
        grid.innerHTML = `<div class="loading" style="color: var(--accent-red);">Error loading screeners: ${error.message}</div>`;
    }
}

// Create a screener card element
function createScreenerCard(screener) {
    const card = document.createElement('div');
    card.className = 'screener-card';

    card.innerHTML = `
        <h3>${screener.name}</h3>
        <p>${screener.description || 'No description available'}</p>
        <button class="btn-run" onclick="runScreener('${screener.name}')">
            Run Screener
        </button>
    `;

    return card;
}

// Run a screener
async function runScreener(name) {
    const button = event.target;
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Running...';

    try {
        const response = await fetch(`/api/screeners/${name}/run`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to run screener');
        }

        const data = await response.json();
        currentResults = data;

        displayResults(data);
    } catch (error) {
        console.error('Error running screener:', error);
        alert(`Error: ${error.message}`);
    } finally {
        button.disabled = false;
        button.textContent = 'Run Screener';
    }
}

// Display screener results
function displayResults(data) {
    // Show market context
    const contextDiv = document.getElementById('market-context');
    document.getElementById('session-name').textContent = data.market_context.session;
    document.getElementById('market-name').textContent = data.market_context.market;
    document.getElementById('market-date').textContent = data.market_context.date;
    document.getElementById('universe-name').textContent = `${data.universe.name} (${data.universe.total_symbols} symbols)`;
    contextDiv.style.display = 'flex';

    // Show results section
    const resultsSection = document.getElementById('results-section');
    const resultsTitle = document.getElementById('results-title');
    const resultsInfo = document.getElementById('results-info');

    resultsTitle.textContent = `${capitalizeFirst(data.screener)} - ${data.count} Results`;

    // Build config display
    let configHtml = '';
    if (data.resolved_config) {
        const config = data.resolved_config;
        configHtml = '<div style="margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 4px;">';
        configHtml += `<strong>Configuration for ${config.session} session:</strong><br>`;

        // Field mappings
        if (config.field_mapping && Object.keys(config.field_mapping).length > 0) {
            configHtml += '<div style="margin-top: 5px;"><em>Field Mappings:</em><br>';
            for (const [field, value] of Object.entries(config.field_mapping)) {
                configHtml += `<span style="margin-left: 10px; font-family: monospace; font-size: 0.9em;">${field}: ${value}</span><br>`;
            }
            configHtml += '</div>';
        }

        // Thresholds
        if (config.thresholds && Object.keys(config.thresholds).length > 0) {
            configHtml += '<div style="margin-top: 5px;"><em>Thresholds:</em><br>';
            for (const [threshold, value] of Object.entries(config.thresholds)) {
                configHtml += `<span style="margin-left: 10px; font-family: monospace; font-size: 0.9em;">${threshold}: ${value}</span><br>`;
            }
            configHtml += '</div>';
        }

        configHtml += '</div>';
    }

    resultsInfo.innerHTML = `
        <strong>${data.description}</strong><br>
        Session: ${data.market_context.session} |
        Market: ${data.market_context.market} |
        Date: ${data.market_context.date}
        ${configHtml}
    `;

    resultsSection.style.display = 'block';

    // Populate table
    if (data.results.length === 0) {
        document.getElementById('results-thead').innerHTML = '';
        document.getElementById('results-tbody').innerHTML = '<tr><td colspan="100%" style="text-align: center; padding: 40px; color: var(--text-secondary);">No results found</td></tr>';
        return;
    }

    const thead = document.getElementById('results-thead');
    const tbody = document.getElementById('results-tbody');

    // Use display columns from YAML config
    const displayColumns = data.display_columns || [];

    // Build table headers from display config
    thead.innerHTML = `
        <tr>
            ${displayColumns.map(col => {
                const colName = typeof col === 'string' ? col : col.name;
                return `<th onclick="sortTableByColumn(this)">${colName}</th>`;
            }).join('')}
        </tr>
    `;

    // Build table rows using display config
    tbody.innerHTML = data.results.map(result => `
        <tr>
            ${displayColumns.map(col => {
                const field = typeof col === 'string' ? col : col.field;
                const format = typeof col === 'string' ? '' : col.format;
                const value = evaluateFieldExpression(result, field);
                return `<td>${formatValue(value, format)}</td>`;
            }).join('')}
        </tr>
    `).join('');

    // Set up dual scrollbars (top and bottom)
    setupDualScrollbars();

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Setup dual horizontal scrollbars
function setupDualScrollbars() {
    const tableContainer = document.getElementById('table-container');
    const tableScrollTop = document.getElementById('table-scroll-top');
    const tableDummy = document.getElementById('table-scroll-dummy');
    const table = document.getElementById('results-table');

    // Set dummy width to match table width
    tableDummy.style.width = table.offsetWidth + 'px';

    // Sync scroll positions
    tableScrollTop.onscroll = function() {
        tableContainer.scrollLeft = tableScrollTop.scrollLeft;
    };

    tableContainer.onscroll = function() {
        tableScrollTop.scrollLeft = tableContainer.scrollLeft;
    };
}

// Evaluate field expression (handle simple fields and calculated expressions)
function evaluateFieldExpression(result, field) {
    // If field exists directly in result, return it
    if (field in result) {
        return result[field];
    }

    // Handle expressions like "min_close - prevday_close" or "((min_close - day_open) / day_open * 100)"
    try {
        let expr = field;
        // Replace field names with values
        for (const [key, value] of Object.entries(result)) {
            if (value !== null && value !== undefined) {
                // Use word boundaries to avoid partial matches
                const regex = new RegExp(`\\b${key}\\b`, 'g');
                expr = expr.replace(regex, value);
            }
        }
        // Safely evaluate the expression
        return eval(expr);
    } catch (e) {
        return null;
    }
}

// Format value based on format type from YAML
function formatValue(value, format) {
    if (value === null || value === undefined) return '-';

    switch (format) {
        case 'price':
            return `$${Number(value).toFixed(2)}`;

        case 'price_change':
            const num = Number(value);
            const className = num > 0 ? 'positive' : num < 0 ? 'negative' : 'neutral';
            const sign = num > 0 ? '+' : '';
            return `<span class="${className}">${sign}$${num.toFixed(2)}</span>`;

        case 'percent':
            const pct = Number(value);
            const pctClass = pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'neutral';
            const pctSign = pct > 0 ? '+' : '';
            return `<span class="${pctClass}">${pctSign}${pct.toFixed(2)}%</span>`;

        case 'volume':
            return formatVolume(value);

        default:
            // Numbers
            if (typeof value === 'number') {
                return value.toLocaleString();
            }
            return value;
    }
}

// Format table header
function formatHeader(header) {
    // Abbreviation mapping for common long headers
    const abbreviations = {
        'min_accumulated_volume': 'PM Volume',
        'min_timestamp_formatted': 'Time',
        'prevday_close': 'Prev Close',
        'prevday_volume': 'Prev Vol',
        'prevday_high': 'Prev High',
        'prevday_low': 'Prev Low',
        'day_open': 'Open',
        'day_close': 'Close',
        'day_high': 'High',
        'day_low': 'Low',
        'day_volume': 'Volume',
        'min_close': 'PM Price',
        'market_cap': 'Mkt Cap',
        'pm_change': 'PM Change',
        'pm_gap_percent': 'PM Gap %',
        'ah_change': 'AH Change',
        'ah_change_percent': 'AH Change %',
        'intraday_change': 'Change',
        'intraday_change_percent': 'Change %',
        'day_change': 'Change',
        'day_change_percent': 'Change %'
    };

    // Check if there's a predefined abbreviation
    if (abbreviations[header]) {
        return abbreviations[header];
    }

    // Default formatting
    return header
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Format table cell based on field name and value
function formatCell(field, value) {
    if (value === null || value === undefined) return '-';

    const fieldLower = field.toLowerCase();

    // Price fields
    if (fieldLower.includes('price') || fieldLower.includes('close') || fieldLower.includes('open') ||
        fieldLower.includes('high') || fieldLower.includes('low')) {
        return `$${Number(value).toFixed(2)}`;
    }

    // Percentage fields
    if (fieldLower.includes('percent') || fieldLower.includes('pct') || fieldLower.includes('change%') ||
        fieldLower.includes('gap_percent') || fieldLower.includes('change_percent')) {
        const num = Number(value);
        const className = num > 0 ? 'positive' : num < 0 ? 'negative' : 'neutral';
        const sign = num > 0 ? '+' : '';
        return `<span class="${className}">${sign}${num.toFixed(2)}%</span>`;
    }

    // Change fields (dollar amounts)
    if ((fieldLower.includes('change') || fieldLower.includes('gap')) && !fieldLower.includes('percent')) {
        const num = Number(value);
        const className = num > 0 ? 'positive' : num < 0 ? 'negative' : 'neutral';
        const sign = num > 0 ? '+' : '';
        return `<span class="${className}">${sign}$${Math.abs(num).toFixed(2)}</span>`;
    }

    // Volume fields
    if (fieldLower.includes('volume')) {
        return formatVolume(value);
    }

    // Market cap
    if (fieldLower.includes('market_cap') || fieldLower.includes('marketcap')) {
        return formatMarketCap(value);
    }

    // Numbers
    if (typeof value === 'number') {
        return value.toLocaleString();
    }

    return value;
}

// Format volume with K/M/B suffixes
function formatVolume(volume) {
    const num = Number(volume);
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toFixed(0);
}

// Format market cap
function formatMarketCap(value) {
    const num = Number(value);
    if (num >= 1e12) return '$' + (num / 1e12).toFixed(2) + 'T';
    if (num >= 1e9) return '$' + (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return '$' + (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return '$' + (num / 1e3).toFixed(2) + 'K';
    return '$' + num.toFixed(0);
}

// Sort table by column
function sortTable(field) {
    if (!currentResults || !currentResults.results.length) return;

    const tbody = document.getElementById('results-tbody');
    const headers = Object.keys(currentResults.results[0]);

    // Toggle sort direction
    const currentSort = tbody.dataset.sortField;
    const currentDir = tbody.dataset.sortDir || 'asc';
    const newDir = (currentSort === field && currentDir === 'asc') ? 'desc' : 'asc';

    // Sort results
    const sorted = [...currentResults.results].sort((a, b) => {
        const aVal = a[field];
        const bVal = b[field];

        if (aVal === null || aVal === undefined) return 1;
        if (bVal === null || bVal === undefined) return -1;

        if (typeof aVal === 'number' && typeof bVal === 'number') {
            return newDir === 'asc' ? aVal - bVal : bVal - aVal;
        }

        const aStr = String(aVal);
        const bStr = String(bVal);
        return newDir === 'asc' ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    });

    // Update display
    tbody.innerHTML = sorted.map(result => `
        <tr>
            ${headers.map(header => `<td>${formatCell(header, result[header])}</td>`).join('')}
        </tr>
    `).join('');

    // Store sort state
    tbody.dataset.sortField = field;
    tbody.dataset.sortDir = newDir;
}

// Close results section
function closeResults() {
    document.getElementById('results-section').style.display = 'none';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Export results to CSV
function exportToCSV() {
    if (!currentResults || !currentResults.results.length) return;

    const headers = Object.keys(currentResults.results[0]);
    const csvContent = [
        // Headers
        headers.join(','),
        // Data rows
        ...currentResults.results.map(row =>
            headers.map(header => {
                const value = row[header];
                // Escape quotes and wrap in quotes if contains comma
                const escaped = String(value).replace(/"/g, '""');
                return escaped.includes(',') ? `"${escaped}"` : escaped;
            }).join(',')
        )
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentResults.screener}_${currentResults.market_context.date}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// Helper: Capitalize first letter
function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
