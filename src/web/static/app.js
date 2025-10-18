// TradeScout Web Interface - JavaScript

let currentResults = null;

// Load screeners and market context on page load
document.addEventListener('DOMContentLoaded', () => {
    loadMarketContext();
    loadScreeners();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('close-results').addEventListener('click', closeResults);
    document.getElementById('export-csv').addEventListener('click', exportToCSV);
    document.getElementById('market-update-btn').addEventListener('click', updateMarketData);
}

// Fetch and display market context
async function loadMarketContext() {
    try {
        const response = await fetch('/api/market/context');
        if (!response.ok) throw new Error('Failed to load market context');

        const context = await response.json();

        // Show market context section
        const contextDiv = document.getElementById('market-context');
        document.getElementById('session-name').textContent = context.trading_status.session_name;
        // Hide the market item since we show breakdown below
        document.getElementById('market-name').parentElement.style.display = 'none';
        document.getElementById('market-date').textContent = context.dates.current_date;

        // Build universe text
        document.getElementById('universe-name').textContent =
            `${context.universe.name} (${context.universe.total_assets.toLocaleString()} symbols)`;

        // Add market breakdown as separate lines below universe
        const universeItem = document.getElementById('universe-name').parentElement;

        // Remove any existing breakdown items
        let nextItem = universeItem.nextElementSibling;
        while (nextItem && nextItem.classList.contains('context-item-breakdown')) {
            const toRemove = nextItem;
            nextItem = nextItem.nextElementSibling;
            toRemove.remove();
        }

        // Add new breakdown items
        context.universe.market_breakdown.forEach(m => {
            const breakdownItem = document.createElement('div');
            breakdownItem.className = 'context-item context-item-breakdown';
            breakdownItem.innerHTML = `
                <span class="context-label">  └─ ${m.name}:</span>
                <span class="context-value">${m.count.toLocaleString()} (${m.percentage.toFixed(1)}%)</span>
            `;
            universeItem.insertAdjacentElement('afterend', breakdownItem);
        });

        // Add last snapshot info if available
        if (context.last_snapshot && context.last_snapshot.age) {
            const snapshotInfo = document.createElement('div');
            snapshotInfo.className = 'context-item';
            snapshotInfo.innerHTML = `
                <span class="context-label">Last Update:</span>
                <span class="context-value">${context.last_snapshot.age}</span>
            `;
            contextDiv.insertBefore(snapshotInfo, document.getElementById('market-update-btn').parentElement);
        }

        contextDiv.style.display = 'flex';
    } catch (error) {
        console.error('Error loading market context:', error);
    }
}

// Update market data
async function updateMarketData() {
    const button = document.getElementById('market-update-btn');
    const originalText = button.textContent;
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Updating...';

    try {
        const response = await fetch('/api/market/update', {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update market data');
        }

        const result = await response.json();

        // Show success message
        if (result.data_was_fresh) {
            alert(`Market data is fresh (within TTL). No update needed.\nLast update: ${result.age_minutes?.toFixed(1)} minutes ago`);
        } else {
            alert(`Market data updated successfully!\n\nSaved: ${result.saved} new records\nDuplicates skipped: ${result.duplicates}\nTotal records: ${result.total_historical_records?.toLocaleString()}`);
        }

        // Reload market context to show updated timestamp
        loadMarketContext();
    } catch (error) {
        console.error('Error updating market data:', error);
        alert(`Error: ${error.message}`);
    } finally {
        button.disabled = false;
        button.textContent = originalText;
    }
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
    // Show market context (simplified for screener results)
    const contextDiv = document.getElementById('market-context');
    document.getElementById('session-name').textContent = data.market_context.session;
    // Keep market hidden since we don't need it
    document.getElementById('market-name').parentElement.style.display = 'none';
    document.getElementById('market-date').textContent = data.market_context.date;
    // Hide universe display for screener results (not in response)
    document.getElementById('universe-name').parentElement.style.display = 'none';
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

    // Build data date display
    let dataDateInfo = '';
    if (data.market_context.data_date && data.market_context.data_date !== data.market_context.date) {
        dataDateInfo = ` | <strong>Data from: ${data.market_context.data_date}</strong>`;
    }

    resultsInfo.innerHTML = `
        <strong>${data.description}</strong><br>
        Session: ${data.market_context.session} |
        Market: ${data.market_context.market} |
        Date: ${data.market_context.date}${dataDateInfo}
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

    // Build table headers from display config with sort indicators
    thead.innerHTML = `
        <tr>
            ${displayColumns.map((col, index) => {
                const colName = typeof col === 'string' ? col : col.name;
                return `<th data-column-index="${index}" onclick="sortTableByColumn(${index})" style="cursor: pointer; user-select: none;">
                    ${colName} <span class="sort-indicator"></span>
                </th>`;
            }).join('')}
        </tr>
    `;

    // Build table rows using display config
    tbody.innerHTML = data.results.map(result => `
        <tr>
            ${displayColumns.map((col, colIndex) => {
                const field = typeof col === 'string' ? col : col.field;
                const format = typeof col === 'string' ? '' : col.format;
                const colName = typeof col === 'string' ? col : col.name;
                const value = evaluateFieldExpression(result, field);

                // Make symbol column clickable
                if (colName.toUpperCase() === 'SYMBOL' && result.symbol) {
                    return `<td><span class="symbol-link" onclick="openAssetModal('${result.symbol}')">${value}</span></td>`;
                }

                return `<td>${formatValue(value, format)}</td>`;
            }).join('')}
        </tr>
    `).join('');

    // Set up dual scrollbars (top and bottom)
    setupDualScrollbars();

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Sort state
let currentSortColumn = null;
let currentSortDirection = 'asc';

// Sort table by column index
function sortTableByColumn(columnIndex) {
    if (!currentResults || !currentResults.results || currentResults.results.length === 0) return;

    const displayColumns = currentResults.display_columns || [];
    const column = displayColumns[columnIndex];
    const field = typeof column === 'string' ? column : column.field;

    // Toggle sort direction if clicking same column
    if (currentSortColumn === columnIndex) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortColumn = columnIndex;
        currentSortDirection = 'asc';
    }

    // Sort the results
    const sortedResults = [...currentResults.results].sort((a, b) => {
        const aVal = evaluateFieldExpression(a, field);
        const bVal = evaluateFieldExpression(b, field);

        // Handle null/undefined values
        if (aVal === null || aVal === undefined) return 1;
        if (bVal === null || bVal === undefined) return -1;

        // Numeric comparison
        if (typeof aVal === 'number' && typeof bVal === 'number') {
            return currentSortDirection === 'asc' ? aVal - bVal : bVal - aVal;
        }

        // String comparison
        const aStr = String(aVal);
        const bStr = String(bVal);
        const comparison = aStr.localeCompare(bStr);
        return currentSortDirection === 'asc' ? comparison : -comparison;
    });

    // Update the results display
    const tbody = document.getElementById('results-tbody');
    tbody.innerHTML = sortedResults.map(result => `
        <tr>
            ${displayColumns.map(col => {
                const field = typeof col === 'string' ? col : col.field;
                const format = typeof col === 'string' ? '' : col.format;
                const colName = typeof col === 'string' ? col : col.name;
                const value = evaluateFieldExpression(result, field);

                // Make symbol column clickable
                if (colName.toUpperCase() === 'SYMBOL' && result.symbol) {
                    return `<td><span class="symbol-link" onclick="openAssetModal('${result.symbol}')">${value}</span></td>`;
                }

                return `<td>${formatValue(value, format)}</td>`;
            }).join('')}
        </tr>
    `).join('');

    // Update sort indicators
    document.querySelectorAll('.sort-indicator').forEach((indicator, index) => {
        if (index === columnIndex) {
            indicator.textContent = currentSortDirection === 'asc' ? ' ▲' : ' ▼';
        } else {
            indicator.textContent = '';
        }
    });
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

        // Replace SQL ABS() function with JavaScript Math.abs()
        expr = expr.replace(/ABS\(/g, 'Math.abs(');

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

// Asset Info Modal Functions

async function openAssetModal(symbol) {
    const modal = document.getElementById('asset-modal');
    const modalSymbol = document.getElementById('modal-symbol');
    const modalLoading = document.getElementById('modal-loading');
    const modalError = document.getElementById('modal-error');
    const modalData = document.getElementById('modal-data');

    // Show modal
    modal.style.display = 'flex';

    // Reset state
    modalSymbol.textContent = symbol;
    modalLoading.style.display = 'block';
    modalError.style.display = 'none';
    modalData.style.display = 'none';

    try {
        // Fetch asset info
        const response = await fetch(`/api/assets/${symbol}/info`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load asset info');
        }

        const data = await response.json();

        // Populate basic info
        document.getElementById('modal-name').textContent = data.asset.asset.name || '-';
        document.getElementById('modal-market').textContent = data.asset.market ? `${data.asset.market.name} (${data.asset.market.code})` : '-';
        document.getElementById('modal-type').textContent = data.asset.asset.type || '-';
        document.getElementById('modal-currency').textContent = data.asset.asset.currency || '-';
        document.getElementById('modal-status').textContent = data.asset.asset.active ? '✅ Active' : '❌ Inactive';
        document.getElementById('modal-universes').textContent = data.asset.universes.join(', ') || 'None';

        // Populate fundamentals if available
        const fundamentalsSection = document.getElementById('modal-fundamentals-section');
        if (data.asset.fundamentals) {
            const fund = data.asset.fundamentals;
            document.getElementById('modal-market-cap').textContent = fund.market_cap_display || '-';
            document.getElementById('modal-shares-out').textContent = fund.shares_outstanding_display || '-';
            document.getElementById('modal-sector').textContent = fund.sector || '-';
            document.getElementById('modal-industry').textContent = fund.industry || '-';
            document.getElementById('modal-pe-ratio').textContent = fund.pe_ratio ? fund.pe_ratio.toFixed(2) : '-';
            document.getElementById('modal-beta').textContent = fund.beta ? fund.beta.toFixed(2) : '-';
            fundamentalsSection.style.display = 'block';
        } else {
            fundamentalsSection.style.display = 'none';
        }

        // Populate price data if available
        const priceSection = document.getElementById('modal-price-section');
        if (data.price) {
            const price = data.price;
            document.getElementById('modal-prev-close').textContent = price.prevday_close ? `$${price.prevday_close.toFixed(2)}` : '-';
            document.getElementById('modal-day-open').textContent = price.day_open ? `$${price.day_open.toFixed(2)}` : '-';
            document.getElementById('modal-day-high').textContent = price.day_high ? `$${price.day_high.toFixed(2)}` : '-';
            document.getElementById('modal-day-low').textContent = price.day_low ? `$${price.day_low.toFixed(2)}` : '-';
            document.getElementById('modal-day-close').textContent = price.day_close ? `$${price.day_close.toFixed(2)}` : '-';
            document.getElementById('modal-day-volume').textContent = price.day_volume ? formatVolume(price.day_volume) : '-';
            priceSection.style.display = 'block';
        } else {
            priceSection.style.display = 'none';
        }

        // Populate news and sentiment section
        const newsSection = document.getElementById('modal-news-section');
        const newsList = document.getElementById('modal-news-list');
        const sentimentSummary = document.getElementById('modal-sentiment-summary');

        if (data.sentiment) {
            const events = data.sentiment.sentiment_events || [];
            const score = data.sentiment.sentiment_score;

            // Populate sentiment summary at top
            if (score) {
                // We have a sentiment score
                document.getElementById('modal-sentiment-score').textContent = score.score.toFixed(2);
                document.getElementById('modal-sentiment-label').textContent = `(${score.sentiment_label})`;
                document.getElementById('modal-sentiment-details').textContent =
                    `${score.total_articles} articles within ${data.sentiment.time_window_days}-day window, ${score.confidence_level} confidence`;

                // Color code the summary border based on sentiment
                sentimentSummary.className = 'modal-sentiment-summary';
                if (score.score > 0.3) {
                    sentimentSummary.classList.add('positive');
                } else if (score.score < -0.3) {
                    sentimentSummary.classList.add('negative');
                } else {
                    sentimentSummary.classList.add('neutral');
                }
            } else if (events.length > 0) {
                // We have events but no score (articles outside time window)
                document.getElementById('modal-sentiment-score').textContent = 'N/A';
                document.getElementById('modal-sentiment-label').textContent = '';
                document.getElementById('modal-sentiment-details').textContent =
                    `No articles within ${data.sentiment.time_window_days}-day window`;
                sentimentSummary.className = 'modal-sentiment-summary neutral';
            } else {
                // No events at all
                document.getElementById('modal-sentiment-score').textContent = 'N/A';
                document.getElementById('modal-sentiment-label').textContent = '';
                document.getElementById('modal-sentiment-details').textContent = '';
                sentimentSummary.className = 'modal-sentiment-summary neutral';
            }

            // Populate news articles
            if (events.length > 0) {
                // Clear existing content
                newsList.innerHTML = '';

                // Show only first 5 articles
                const articlesToShow = events.slice(0, 5);

                articlesToShow.forEach(article => {
                    const articleDiv = document.createElement('div');
                    articleDiv.className = `news-article ${article.sentiment_type.toLowerCase()}`;

                    // Build article HTML
                    let articleHTML = `
                        <div class="news-article-header">
                            <div class="news-article-title">
                                ${article.article_url ?
                                    `<a href="${article.article_url}" target="_blank" rel="noopener noreferrer">${article.title}</a>` :
                                    article.title
                                }
                            </div>
                            <span class="news-article-sentiment ${article.sentiment_type.toLowerCase()}">${article.sentiment_type}</span>
                        </div>
                        <div class="news-article-meta">
                            <span class="news-article-date">${article.event_date} ${article.event_time || ''}</span>
                            <span class="news-article-publisher">${article.publisher}</span>
                        </div>
                    `;

                    // Add reasoning if available
                    if (article.sentiment_reasoning && article.sentiment_reasoning.trim()) {
                        articleHTML += `<div class="news-article-reasoning">${article.sentiment_reasoning}</div>`;
                    }

                    articleDiv.innerHTML = articleHTML;
                    newsList.appendChild(articleDiv);
                });

                newsSection.style.display = 'block';
            } else {
                // Show "no news" message
                newsList.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 20px;">📰 No news articles found for this symbol</div>';
                newsSection.style.display = 'block';
            }
        } else {
            newsSection.style.display = 'none';
        }

        // Show data, hide loading
        modalLoading.style.display = 'none';
        modalData.style.display = 'block';

    } catch (error) {
        console.error('Error loading asset info:', error);
        modalLoading.style.display = 'none';
        modalError.style.display = 'block';
        modalError.textContent = `Error: ${error.message}`;
    }
}

function closeAssetModal() {
    const modal = document.getElementById('asset-modal');
    modal.style.display = 'none';
}
