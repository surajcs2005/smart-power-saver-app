let chart;
let deviceChart;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    fetchDevices();
    setInterval(fetchDevices, 5000); // Update every 5 seconds
    
    // Add event listeners for interactive elements
    setupEventListeners();
});

function setupEventListeners() {
    // Chart timeframe selector
    const timeframeSelect = document.getElementById('chart-timeframe');
    if (timeframeSelect) {
        timeframeSelect.addEventListener('change', function() {
            updateChartTimeframe(this.value);
        });
    }

    // Search and filter handlers
    const search = document.getElementById('device-search');
    const roomFilter = document.getElementById('room-filter');
    const statusFilter = document.getElementById('status-filter');
    ;[search, roomFilter, statusFilter].forEach(el => {
        if (!el) return;
        el.addEventListener('input', applyDeviceFilters);
        el.addEventListener('change', applyDeviceFilters);
    });
}

let latestDevices = [];

function fetchDevices() {
    fetch('/api/devices/')
        .then(res => res.json())
        .then(json => {
            latestDevices = json.devices || [];
            updateDeviceList(latestDevices);
            updateChart(json.devices);
            updateStats(json.devices);
            updateActivityFeed(json.devices);
        })
        .catch(error => {
            console.error('Error fetching devices:', error);
            showError('Failed to fetch device data');
        });
}

function updateDeviceList(devices) {
    const div = document.getElementById('devices');
    if (!div) return;
    
    div.innerHTML = '';
    
    if (devices.length === 0) {
        div.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-microchip"></i>
                <span>No devices found</span>
            </div>
        `;
        return;
    }
    
    const filtered = applyDeviceFilters(devices, true);
    const countEl = document.getElementById('device-count');
    if (countEl) countEl.textContent = `${filtered.length} device${filtered.length === 1 ? '' : 's'}`;

    filtered.forEach(d => {
        const el = document.createElement('div');
        el.className = 'device-item fade-in';
        
        const deviceIcon = getDeviceIcon(d.name);
        const statusClass = d.is_on ? 'online' : 'offline';
        const statusText = d.is_on ? 'ON' : 'OFF';
        const lastSeen = d.last_seen ? formatTimeAgo(new Date(d.last_seen)) : 'Never';
        
        el.innerHTML = `
            <div class="device-info">
                <div class="device-icon">
                    <i class="${deviceIcon}"></i>
                </div>
                <div class="device-details">
                    <h4>${d.name}</h4>
                    <p>Room: ${d.room || 'Unknown'}</p>
                    <div class="device-status ${statusClass}">
                        <i class="fas fa-circle"></i>
                        ${statusText} • Last seen: ${lastSeen}
                    </div>
                </div>
            </div>
            <div class="device-actions">
                <button class="btn btn-sm ${d.is_on ? 'btn-danger' : 'btn-primary'}" onclick="toggleDevice(${d.id})">
                    <i class="fas fa-power-off"></i>
                    ${d.is_on ? 'Turn OFF' : 'Turn ON'}
                </button>
                <button class="btn btn-sm btn-secondary" onclick="showDeviceDetails(${d.id})">
                    <i class="fas fa-info-circle"></i>
                </button>
            </div>
        `;
        div.appendChild(el);
    });
}

function applyDeviceFilters(devices = latestDevices, returnListOnly = false) {
    const search = (document.getElementById('device-search')?.value || '').toLowerCase();
    const room = (document.getElementById('room-filter')?.value || '').toLowerCase();
    const status = (document.getElementById('status-filter')?.value || '').toLowerCase();

    const result = devices.filter(d => {
        const matchesSearch = !search || `${d.name} ${d.room}`.toLowerCase().includes(search);
        const matchesRoom = !room || (d.room || '').toLowerCase() === room;
        const matchesStatus = !status || (status === 'on' ? d.is_on : !d.is_on);
        return matchesSearch && matchesRoom && matchesStatus;
    });

    if (returnListOnly) return result;
    updateDeviceList(result);
    return result;
}

function getDeviceIcon(deviceName) {
    const name = deviceName.toLowerCase();
    if (name.includes('light') || name.includes('lamp')) return 'fas fa-lightbulb';
    if (name.includes('tv') || name.includes('television')) return 'fas fa-tv';
    if (name.includes('fan')) return 'fas fa-fan';
    if (name.includes('heater') || name.includes('cooler')) return 'fas fa-thermometer-half';
    if (name.includes('computer') || name.includes('pc')) return 'fas fa-desktop';
    if (name.includes('phone') || name.includes('mobile')) return 'fas fa-mobile-alt';
    if (name.includes('router') || name.includes('wifi')) return 'fas fa-wifi';
    return 'fas fa-microchip';
}

function toggleDevice(id) {
    const button = event.target.closest('button');
    const originalText = button.innerHTML;
    
    // Show loading state
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
    button.disabled = true;
    
    fetch(`/api/toggle/${id}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Add success animation
        button.innerHTML = '<i class="fas fa-check"></i> Updated!';
        button.style.background = '#10b981';
        
        setTimeout(() => {
            fetchDevices(); // Refresh the device list
        }, 1000);
    })
    .catch(error => {
        console.error('Error toggling device:', error);
        button.innerHTML = originalText;
        button.disabled = false;
        showError('Failed to update device');
    });
}

function updateChart(devices) {
    const ctx = document.getElementById('mainChart');
    if (!ctx) return;
    
    const labels = devices.map(d => d.name);
    const data = devices.map(d => {
        const latestLog = d.recent_logs?.at(-1);
        return latestLog ? latestLog.power_watts : 0;
    });
    
    const colors = devices.map((_, index) => {
        const hue = (index * 137.5) % 360; // Golden angle for good color distribution
        return `hsl(${hue}, 70%, 50%)`;
    });
    
    if (chart) {
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.data.datasets[0].backgroundColor = colors;
        chart.update('active');
    } else {
        chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Power Usage (W)',
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.parsed}W`;
                            }
                        }
                    }
                },
                cutout: '60%',
                animation: {
                    animateRotate: true,
                    animateScale: true
                }
            }
        });
    }
}

function updateStats(devices) {
    const totalDevices = devices.length;
    const activeDevices = devices.filter(d => d.is_on).length;
    const totalPower = devices.reduce((sum, d) => {
        const latestLog = d.recent_logs?.at(-1);
        return sum + (latestLog ? latestLog.power_watts : 0);
    }, 0);
    
    // Calculate estimated monthly savings (simplified calculation)
    const monthlySavings = (totalPower * 6.0 * 24 * 30) / 1000; // Assuming ₹6.0/kWh
    
    // Update stat cards
    updateStatCard('total-devices', totalDevices);
    updateStatCard('active-devices', activeDevices);
    updateStatCard('total-power', `${Math.round(totalPower)}W`);
    updateStatCard('savings', `₹${monthlySavings.toFixed(2)}`);
    
    // Update analytics
    const avgUsage = totalDevices > 0 ? totalPower / totalDevices : 0;
    const peakUsage = Math.max(...devices.map(d => {
        const latestLog = d.recent_logs?.at(-1);
        return latestLog ? latestLog.power_watts : 0;
    }));
    
    updateAnalyticsCard('avg-usage', `${Math.round(avgUsage)}W`);
    updateAnalyticsCard('peak-usage', `${Math.round(peakUsage)}W`);
    updateAnalyticsCard('daily-usage', `${(totalPower * 24 / 1000).toFixed(1)}kWh`);
    updateAnalyticsCard('efficiency', `${Math.round((activeDevices / totalDevices) * 100)}%`);
}

function updateStatCard(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
        element.classList.add('slide-up');
        setTimeout(() => element.classList.remove('slide-up'), 300);
    }
}

function updateAnalyticsCard(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function updateActivityFeed(devices) {
    const feed = document.getElementById('activity-feed');
    if (!feed) return;
    
    // Clear existing activities except the first one
    const activities = feed.querySelectorAll('.activity-item');
    for (let i = 1; i < activities.length; i++) {
        activities[i].remove();
    }
    
    // Add recent device activities
    devices.forEach(device => {
        if (device.recent_logs && device.recent_logs.length > 0) {
            const latestLog = device.recent_logs[device.recent_logs.length - 1];
            const timestamp = new Date(latestLog.timestamp);
            const power = latestLog.power_watts;
            
            const activityItem = document.createElement('div');
            activityItem.className = 'activity-item fade-in';
            activityItem.innerHTML = `
                <div class="activity-icon">
                    <i class="fas fa-bolt"></i>
                </div>
                <div class="activity-content">
                    <span class="activity-text">${device.name} consuming ${power}W</span>
                    <span class="activity-time">${formatTimeAgo(timestamp)}</span>
                </div>
            `;
            feed.appendChild(activityItem);
        }
    });
}

function showDeviceDetails(deviceId) {
    // This would open a modal with detailed device information
    console.log('Showing details for device:', deviceId);
    // For now, just show an alert
    alert(`Device details for ID: ${deviceId}\nThis feature will be implemented in the modal.`);
}

function refreshDevices() {
    const refreshBtn = document.querySelector('[onclick="refreshDevices()"]');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
        refreshBtn.disabled = true;
    }
    
    fetchDevices();
    
    setTimeout(() => {
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
            refreshBtn.disabled = false;
        }
    }, 1000);
}

function updateChartTimeframe(timeframe) {
    console.log('Updating chart timeframe to:', timeframe);
    // This would update the chart data based on the selected timeframe
    // Implementation would depend on backend API changes
}

function showError(message) {
    // Create a toast notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        z-index: 3000;
        animation: slideInRight 0.3s ease;
    `;
    toast.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatTimeAgo(date) {
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
}

// Modal functions
function closeModal() {
    const modal = document.getElementById('device-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function closeAddDeviceModal() {
    const modal = document.getElementById('add-device-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);
