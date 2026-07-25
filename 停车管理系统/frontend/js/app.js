// API基础URL
const API_BASE = '/api';

// ==================== 工具函数 ====================

// 显示提示消息
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ==================== 页面初始化 ====================

// 页面加载完成后自动加载数据
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();

    // 设置定时器，每60秒（1分钟）刷新一次数据并检查违约预约
    setInterval(async () => {
        // 检查违约预约
        await checkReservationViolation();

        // 获取当前活动页面并刷新数据
        const activePage = document.querySelector('.nav-item.active');
        if (activePage) {
            const pageName = activePage.dataset.page;
            await loadPageData(pageName);
        }
    }, 60000); // 60000毫秒 = 60秒
});

// 检查违约预约
async function checkReservationViolation() {
    try {
        const response = await fetch(`${API_BASE}/reservations/check-violation`);
        const result = await response.json();

        if (result.success && result.violation_count > 0) {
            showToast(`检测到${result.violation_count}条违约预约，已自动处理`, 'warning');
        }
    } catch (error) {
        console.error('检查违约预约失败:', error);
    }
}

// ==================== 页面导航 ====================

// 导航切换
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();

        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');

        // 切换页面
        const pageName = item.dataset.page;
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        document.getElementById(`${pageName}-page`).classList.add('active');

        // 更新页面标题
        document.getElementById('page-title').textContent = item.querySelector('span').textContent;

        // 加载页面数据
        loadPageData(pageName);
    });
});

// 加载页面数据
async function loadPageData(pageName) {
    switch(pageName) {
        case 'dashboard':
            await loadDashboard();
            break;
        case 'parking':
            await loadParkingSpaces();
            break;
        case 'reservations':
            await loadReservations();
            break;
        case 'vehicles':
            await loadVehiclesManagement();
            break;
        case 'users':
            await loadUsers();
            break;
        case 'records':
            await loadRecords();
            break;
    }
}

// ==================== 数据概览 ====================

async function loadDashboard() {
    try {
        const response = await fetch(`${API_BASE}/parking/stats`);
        const data = await response.json();

        if (data.success) {
            // 更新统计卡片
            const totalSpaces = data.area_stats.reduce((sum, item) => sum + item.total, 0);
            const availableSpaces = data.area_stats.reduce((sum, item) => sum + item.available, 0);
            const occupiedSpaces = data.area_stats.reduce((sum, item) => sum + item.occupied, 0);
            const reservedSpaces = data.area_stats.reduce((sum, item) => sum + item.reserved, 0);

            document.getElementById('total-spaces').textContent = totalSpaces;
            document.getElementById('available-spaces').textContent = availableSpaces;
            document.getElementById('occupied-spaces').textContent = occupiedSpaces;
            document.getElementById('reserved-spaces').textContent = reservedSpaces;

            // 渲染区域图表
            renderAreaChart(data.area_stats);

            // 渲染类型图表
            renderTypeChart(data.type_stats);
        }
    } catch (error) {
        console.error('加载统计数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

function renderAreaChart(areaStats) {
    const chartContainer = document.getElementById('area-chart');
    chartContainer.innerHTML = '';

    const maxValue = Math.max(...areaStats.map(item => item.total));

    areaStats.forEach(item => {
        const barGroup = document.createElement('div');
        barGroup.className = 'bar-group';

        barGroup.innerHTML = `
            <div class="bar-container">
                <div class="bar available" style="height: ${(item.available / maxValue) * 100}%" data-value="${item.available}"></div>
                <div class="bar occupied" style="height: ${(item.occupied / maxValue) * 100}%" data-value="${item.occupied}"></div>
                <div class="bar reserved" style="height: ${(item.reserved / maxValue) * 100}%" data-value="${item.reserved}"></div>
            </div>
            <div class="bar-label">${item.area}</div>
        `;

        chartContainer.appendChild(barGroup);
    });
}

function renderTypeChart(typeStats) {
    const chartContainer = document.getElementById('type-chart');
    chartContainer.innerHTML = '';

    const maxValue = Math.max(...typeStats.map(item => item.total));

    typeStats.forEach(item => {
        const barGroup = document.createElement('div');
        barGroup.className = 'bar-group';

        barGroup.innerHTML = `
            <div class="bar-container">
                <div class="bar available" style="height: ${(item.available / maxValue) * 100}%" data-value="${item.available}"></div>
                <div class="bar occupied" style="height: ${(item.occupied / maxValue) * 100}%" data-value="${item.occupied}"></div>
                <div class="bar reserved" style="height: ${(item.reserved / maxValue) * 100}%" data-value="${item.reserved}"></div>
            </div>
            <div class="bar-label">${item.type_name}</div>
        `;

        chartContainer.appendChild(barGroup);
    });
}

// ==================== 车位管理 ====================

async function loadParkingSpaces() {
    try {
        const area = document.getElementById('area-filter').value;
        const type_id = document.getElementById('type-filter').value;
        const status = document.getElementById('status-filter').value;

        const params = new URLSearchParams();
        if (area) params.append('area', area);
        if (type_id) params.append('type_id', type_id);
        if (status) params.append('status', status);

        const response = await fetch(`${API_BASE}/parking/spaces?${params}`);
        const data = await response.json();

        if (data.success) {
            renderParkingSpaces(data.spaces);
        }
    } catch (error) {
        console.error('加载车位数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

function renderParkingSpaces(spaces) {
    const tbody = document.getElementById('spaces-table-body');
    tbody.innerHTML = '';

    spaces.forEach(space => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${space.number}</td>
            <td>${space.area}</td>
            <td>${space.type_name}</td>
            <td><span class="status-badge ${space.status}">${space.status}</span></td>
            <td>
                <button class="action-btn btn-view" onclick="viewSpaceDetails(${space.id})">查看</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 筛选和刷新按钮事件
document.getElementById('area-filter').addEventListener('change', loadParkingSpaces);
document.getElementById('type-filter').addEventListener('change', loadParkingSpaces);
document.getElementById('status-filter').addEventListener('change', loadParkingSpaces);
document.getElementById('refresh-spaces').addEventListener('click', loadParkingSpaces);

// ==================== 预约管理 ====================

async function loadReservations() {
    try {
        const status = document.getElementById('reservation-status-filter').value;

        const params = new URLSearchParams();
        if (status) params.append('status', status);

        const response = await fetch(`${API_BASE}/reservations?${params}`);
        const data = await response.json();

        if (data.success) {
            renderReservations(data.reservations);
        }
    } catch (error) {
        console.error('加载预约数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

function renderReservations(reservations) {
    const tbody = document.getElementById('reservations-table-body');
    tbody.innerHTML = '';

    reservations.forEach(reservation => {
        const tr = document.createElement('tr');

        let actions = '';
        if (reservation.status === '待审批') {
            actions = `
                <button class="action-btn btn-approve" onclick="approveReservation(${reservation.id}, true)">批准</button>
                <button class="action-btn btn-reject" onclick="approveReservation(${reservation.id}, false)">拒绝</button>
                <button class="action-btn btn-cancel" onclick="cancelReservation(${reservation.id}, ${reservation.user_id || 'null'})">取消</button>
            `;
        } else if (reservation.status === '已批准') {
            actions = `
                <button class="action-btn btn-cancel" onclick="cancelReservation(${reservation.id}, ${reservation.user_id || 'null'})">取消</button>
                <button class="action-btn btn-view" onclick="viewReservationDetails(${reservation.id})">查看</button>
            `;
        } else {
            actions = '<button class="action-btn btn-view" onclick="viewReservationDetails(${reservation.id})">查看</button>';
        }

        tr.innerHTML = `
            <td>${reservation.id}</td>
            <td>${reservation.user_name} (${reservation.user_type})</td>
            <td>${reservation.plate}</td>
            <td>${reservation.space_number} (${reservation.area})</td>
            <td>${reservation.start_time}</td>
            <td>${reservation.end_time}</td>
            <td><span class="status-badge ${reservation.status}">${reservation.status}</span></td>
            <td>${actions}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function approveReservation(reservationId, approve) {
    try {
        const response = await fetch(`${API_BASE}/reservations/${reservationId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ approve })
        });

        const data = await response.json();

        if (data.success) {
            showToast(approve ? '预约已批准' : '预约已拒绝', 'success');
            await loadReservations();
        } else {
            showToast(data.message || '操作失败', 'error');
        }
    } catch (error) {
        console.error('审批预约失败:', error);
        showToast('操作失败', 'error');
    }
}

async function cancelReservation(reservationId, userId) {
    if (!confirm('确定要取消这个预约吗？')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/reservations/${reservationId}/cancel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                user_id: userId,
                reason: '用户主动取消'
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('预约已取消', 'success');
            await loadReservations();
        } else {
            showToast(data.message || '取消失败', 'error');
        }
    } catch (error) {
        console.error('取消预约失败:', error);
        showToast('取消失败', 'error');
    }
}

async function viewReservationDetails(reservationId) {
    try {
        const response = await fetch(`${API_BASE}/reservations`);
        const data = await response.json();

        if (data.success) {
            const reservation = data.reservations.find(r => r.id === reservationId);
            if (reservation) {
                const details = `
                    预约ID: ${reservation.id}
                    用户: ${reservation.user_name} (${reservation.user_type})
                    车牌号: ${reservation.plate}
                    车辆类型: ${reservation.vehicle_type}
                    车位: ${reservation.space_number} (${reservation.area})
                    车位类型: ${reservation.space_type}
                    开始时间: ${reservation.start_time}
                    结束时间: ${reservation.end_time}
                    用途: ${reservation.purpose || '无'}
                    状态: ${reservation.status}
                `;
                alert(details);
            }
        }
    } catch (error) {
        console.error('获取预约详情失败:', error);
        showToast('获取详情失败', 'error');
    }
}

// 筛选和刷新按钮事件
document.getElementById('reservation-status-filter').addEventListener('change', loadReservations);
document.getElementById('refresh-reservations').addEventListener('click', loadReservations);

// 加载表单所需的数据
async function loadFormData() {
    try {
        // 加载用户数据
        const usersResponse = await fetch(`${API_BASE}/users`);

        if (!usersResponse.ok) {
            throw new Error(`HTTP error! status: ${usersResponse.status}`);
        }

        const usersData = await usersResponse.json();
        if (usersData.success) {
            const userSelect = document.getElementById('reservation-user');
            userSelect.innerHTML = '<option value="">请选择用户（不选则只能选择公务车或特殊车辆）</option>';
            usersData.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = `${user.name} (${user.type})`;
                userSelect.appendChild(option);
            });
        } else {
            throw new Error(usersData.message || '加载用户数据失败');
        }

        // 加载车位类型数据
        const typesResponse = await fetch(`${API_BASE}/parking/types`);

        if (!typesResponse.ok) {
            throw new Error(`HTTP error! status: ${typesResponse.status}`);
        }

        const typesData = await typesResponse.json();
        if (typesData.success) {
            const typeSelect = document.getElementById('reservation-type');
            typeSelect.innerHTML = '<option value="">所有可用类型</option>';
            typesData.types.forEach(type => {
                const option = document.createElement('option');
                option.value = type.id;
                option.textContent = type.name;
                typeSelect.appendChild(option);
            });
        } else {
            throw new Error(typesData.message || '加载车位类型失败');
        }
    } catch (error) {
        console.error('加载表单数据失败:', error);
        showToast('加载表单数据失败: ' + error.message, 'error');
    }
}

// 加载车辆列表
async function loadVehicles(userId = null) {
    try {
        console.log('开始加载车辆，userId:', userId);
        const vehicleSelect = document.getElementById('reservation-vehicle');
        vehicleSelect.innerHTML = '<option value="">请选择车辆</option>';

        let response;
        let url;
        if (userId) {
            // 加载指定用户的车辆
            url = `${API_BASE}/vehicles/user/${userId}`;
            console.log('请求URL:', url);
            response = await fetch(url);
        } else {
            // 加载公共车辆（公务车辆和特殊车辆）
            url = `${API_BASE}/vehicles/public`;
            console.log('请求URL:', url);
            response = await fetch(url);
        }

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('返回的数据:', data);

        if (data.success) {
            console.log('车辆数量:', data.vehicles.length);
            if (data.vehicles.length === 0) {
                showToast('该用户没有车辆', 'info');
            }
            data.vehicles.forEach(vehicle => {
                console.log('添加车辆:', vehicle);
                const option = document.createElement('option');
                option.value = vehicle.plate;
                option.dataset.type = vehicle.type;
                option.textContent = `${vehicle.plate} (${vehicle.type})`;
                vehicleSelect.appendChild(option);
            });
            console.log('车辆选项已更新');
        } else {
            throw new Error(data.message || '加载车辆数据失败');
        }
    } catch (error) {
        console.error('加载车辆数据失败:', error);
        showToast('加载车辆数据失败: ' + error.message, 'error');
    }
}

// 保存所有可用车位的选项
let allSpaceOptions = [];

// 根据车辆类型获取可用的车位类型名称
function getValidSpaceTypes(clType) {
    switch(clType) {
        case '公务车辆':
            return ['公务车位', '充电桩'];
        case '特殊车辆':
            return ['临时车位', '充电桩'];
        case '教职工':
            return ['固定车位', '临时车位', '充电桩'];
        case '学生':
        case '访客':
            return ['临时车位', '充电桩'];
        default:
            return [];
    }
}

// 加载可用车位
async function loadAvailableSpaces(clType, area = null, typeId = null) {
    try {
        console.log('loadAvailableSpaces函数被调用');
        console.log('参数类型检查:', {
            clType: clType,
            clTypeType: typeof clType,
            clTypeValue: clType ? clType.toString() : 'null/undefined',
            area: area,
            areaType: typeof area,
            typeId: typeId,
            typeIdType: typeof typeId
        });

        console.log('开始加载可用车位，参数:', { clType, area, typeId });

        if (!clType) {
            console.log('clType为空，返回');
            showToast('请先选择车辆', 'error');
            return;
        }

        const params = new URLSearchParams();
        params.append('cl_type', clType);
        if (area) params.append('area', area);
        // 注意：不传递typeId参数，让存储过程根据车辆类型自动返回所有可用的车位类型

        const url = `${API_BASE}/parking/available?${params}`;
        console.log('请求URL:', url);

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('返回的数据:', data);

        if (data.success) {
            const spaceSelect = document.getElementById('reservation-space');
            spaceSelect.innerHTML = '<option value="">请选择车位</option>';

            // 清空并重新填充所有车位选项
            allSpaceOptions = [];

            if (data.spaces.length === 0) {
                console.log('没有找到可用的车位');
                showToast('没有可用的车位', 'info');
            } else {
                console.log(`找到 ${data.spaces.length} 个可用车位`);
            }

            // 根据车辆类型和区域过滤车位
            data.spaces.forEach(space => {
                const option = document.createElement('option');
                option.value = space.id;
                option.dataset.typeId = space.type_id;
                option.dataset.typeName = space.type_name;
                option.dataset.area = space.area;
                option.textContent = `${space.number} (${space.area} - ${space.type_name})`;

                // 保存到全局数组
                allSpaceOptions.push(option);
                spaceSelect.appendChild(option);
            });

            // 更新车位类型选项 - 只显示与当前车辆类型匹配的车位类型
            const typeSelect = document.getElementById('reservation-type');
            const currentTypeValue = typeSelect.value;
            typeSelect.innerHTML = '<option value="">所有可用类型</option>';

            // 获取当前车辆类型可用的车位类型名称
            const validTypeNames = getValidSpaceTypes(clType);
            console.log('车辆类型', clType, '可用的车位类型:', validTypeNames);

            // 从返回的数据中过滤出匹配的车位类型
            const uniqueTypes = [...new Set(data.spaces.map(s => s.type_id))];
            console.log('API返回的车位类型ID:', uniqueTypes);

            uniqueTypes.forEach(typeId => {
                const space = data.spaces.find(s => s.type_id === typeId);
                if (space && validTypeNames.includes(space.type_name)) {
                    const option = document.createElement('option');
                    option.value = space.type_id;
                    option.textContent = space.type_name;
                    typeSelect.appendChild(option);
                }
            });

            // 如果之前选择的类型在可用类型中，则恢复选择
            if (currentTypeValue && uniqueTypes.includes(parseInt(currentTypeValue))) {
                typeSelect.value = currentTypeValue;
            }
        } else {
            throw new Error(data.message || '加载可用车位失败');
        }
    } catch (error) {
        console.error('加载可用车位失败:', error);
        showToast('加载可用车位失败: ' + error.message, 'error');
    }
}

// 打开新建预约弹窗
document.getElementById('add-reservation-btn').addEventListener('click', async () => {
    await loadFormData();
    document.getElementById('reservation-form').reset();
    // 加载公共车辆（公务车辆和特殊车辆）
    await loadVehicles(null);
    document.getElementById('reservation-modal').classList.remove('hidden');
});

// 关闭弹窗
document.querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('reservation-modal').classList.add('hidden');
});

document.querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('reservation-modal').classList.add('hidden');
});

// 用户选择变化时加载对应的车辆
document.getElementById('reservation-user').addEventListener('change', async (e) => {
    const userId = e.target.value ? parseInt(e.target.value) : null;
    await loadVehicles(userId);

    // 重置车辆、车位类型和车位选择
    document.getElementById('reservation-vehicle').value = '';
    document.getElementById('reservation-type').value = '';
    document.getElementById('reservation-space').value = '';
});

// 车辆选择变化时加载可用车位
document.getElementById('reservation-vehicle').addEventListener('change', async (e) => {
    const selectedOption = e.target.selectedOptions[0];
    if (!selectedOption || !selectedOption.value) {
        return;
    }

    const clType = selectedOption.dataset.type;
    const area = document.getElementById('reservation-area').value || null;
    const typeId = document.getElementById('reservation-type').value || null;

    console.log('车辆选择变化:', { clType, area, typeId });
    console.log('准备调用loadAvailableSpaces函数');

    // 清空车位选择
    document.getElementById('reservation-space').innerHTML = '<option value="">请选择车位</option>';

    try {
        // 加载可用车位
        await loadAvailableSpaces(clType, area, typeId);
        console.log('loadAvailableSpaces函数执行完成');
    } catch (error) {
        console.error('loadAvailableSpaces函数执行出错:', error);
        showToast('加载可用车位失败: ' + error.message, 'error');
    }
});

// 区域选择变化时重新加载可用车位
document.getElementById('reservation-area').addEventListener('change', async (e) => {
    const vehicleSelect = document.getElementById('reservation-vehicle');
    const selectedOption = vehicleSelect.selectedOptions[0];

    if (selectedOption && selectedOption.value) {
        const clType = selectedOption.dataset.type;
        const area = e.target.value || null;
        const typeId = document.getElementById('reservation-type').value || null;

        console.log('区域选择变化:', { clType, area, typeId });
        console.log('allSpaceOptions数组长度:', allSpaceOptions.length);

        // 清空车位选择
        const spaceSelect = document.getElementById('reservation-space');
        spaceSelect.innerHTML = '<option value="">请选择车位</option>';

        // 从全局数组中过滤并添加匹配的车位选项
        let matchCount = 0;
        allSpaceOptions.forEach((option, index) => {
            if (option.value) {
                const optionArea = option.dataset.area;
                const optionTypeId = parseInt(option.dataset.typeId);

                console.log(`选项${index}: area=${optionArea}, typeId=${optionTypeId}, text=${option.textContent}`);

                // 检查是否匹配区域和车位类型
                const matchesArea = !area || optionArea === area;
                const matchesType = !typeId || optionTypeId === parseInt(typeId);

                console.log(`匹配检查: matchesArea=${matchesArea}, matchesType=${matchesType}`);

                if (matchesArea && matchesType) {
                    // 克隆选项以避免重复添加
                    const clonedOption = option.cloneNode(true);
                    spaceSelect.appendChild(clonedOption);
                    matchCount++;
                }
            }
        });

        console.log(`过滤后显示 ${matchCount} 个车位`);
    }
});

// 车位类型选择变化时重新加载可用车位
document.getElementById('reservation-type').addEventListener('change', async (e) => {
    const vehicleSelect = document.getElementById('reservation-vehicle');
    const selectedOption = vehicleSelect.selectedOptions[0];

    if (selectedOption && selectedOption.value) {
        const clType = selectedOption.dataset.type;
        const area = document.getElementById('reservation-area').value || null;
        const typeId = e.target.value || null;

        console.log('车位类型选择变化:', { clType, area, typeId });
        console.log('allSpaceOptions数组长度:', allSpaceOptions.length);

        // 清空车位选择
        const spaceSelect = document.getElementById('reservation-space');
        spaceSelect.innerHTML = '<option value="">请选择车位</option>';

        // 从全局数组中过滤并添加匹配的车位选项
        let matchCount = 0;
        allSpaceOptions.forEach((option, index) => {
            if (option.value) {
                const optionArea = option.dataset.area;
                const optionTypeId = parseInt(option.dataset.typeId);

                console.log(`选项${index}: area=${optionArea}, typeId=${optionTypeId}, text=${option.textContent}`);

                // 检查是否匹配区域和车位类型
                const matchesArea = !area || optionArea === area;
                const matchesType = !typeId || optionTypeId === parseInt(typeId);

                console.log(`匹配检查: matchesArea=${matchesArea}, matchesType=${matchesType}`);

                if (matchesArea && matchesType) {
                    // 克隆选项以避免重复添加
                    const clonedOption = option.cloneNode(true);
                    spaceSelect.appendChild(clonedOption);
                    matchCount++;
                }
            }
        });

        console.log(`过滤后显示 ${matchCount} 个车位`);
    }
});

// 提交预约表单
document.getElementById('reservation-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const user_id = document.getElementById('reservation-user').value ? parseInt(document.getElementById('reservation-user').value) : null;
    const cw_id = parseInt(document.getElementById('reservation-space').value);
    const cph_id = document.getElementById('reservation-vehicle').value;
    const start_time = document.getElementById('reservation-start').value;
    const end_time = document.getElementById('reservation-end').value;
    const purpose = document.getElementById('reservation-purpose').value;

    if (!cw_id || !cph_id || !start_time || !end_time) {
        showToast('请填写所有必填项', 'error');
        return;
    }

    // 验证时间
    const startTime = new Date(start_time);
    const endTime = new Date(end_time);
    const now = new Date();

    if (startTime >= endTime) {
        showToast('开始时间必须早于结束时间', 'error');
        return;
    }

    if (startTime < now) {
        showToast('不能预约过去的时间', 'error');
        return;
    }

    // 如果没有选择用户，则必须选择公务车辆或特殊车辆
    if (!user_id) {
        const vehicleSelect = document.getElementById('reservation-vehicle');
        const selectedOption = vehicleSelect.selectedOptions[0];
        if (selectedOption && selectedOption.dataset.type && 
            !['公务车辆', '特殊车辆'].includes(selectedOption.dataset.type)) {
            showToast('未选择用户时只能选择公务车辆或特殊车辆', 'error');
            return;
        }
    }

    try {
        const response = await fetch(`${API_BASE}/reservations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id,
                cw_id,
                cph_id,
                start_time,
                end_time,
                purpose
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            showToast('预约创建成功', 'success');
            document.getElementById('reservation-modal').classList.add('hidden');
            document.getElementById('reservation-form').reset();
            await loadReservations();
        } else {
            throw new Error(data.message || '预约创建失败');
        }
    } catch (error) {
        console.error('创建预约失败:', error);
        showToast('创建预约失败: ' + error.message, 'error');
    }
});

// ==================== 车辆管理 ====================

async function loadVehiclesManagement() {
    try {
        console.log('开始加载车辆数据...');
        const response = await fetch(`${API_BASE}/vehicles`);
        const data = await response.json();

        console.log('车辆数据响应:', data);

        if (data.success) {
            console.log('车辆列表:', data.vehicles);
            renderVehicles(data.vehicles);
        } else {
            console.error('获取车辆数据失败:', data.message);
            showToast(data.message || '获取车辆数据失败', 'error');
        }
    } catch (error) {
        console.error('加载车辆数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

function renderVehicles(vehicles) {
    console.log('开始渲染车辆列表，数量:', vehicles.length);
    const tbody = document.getElementById('vehicles-table-body');
    tbody.innerHTML = '';

    if (vehicles.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td colspan="5" style="text-align: center; padding: 20px;">
                暂无车辆数据
            </td>
        `;
        tbody.appendChild(tr);
        return;
    }

    vehicles.forEach(vehicle => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${vehicle.plate}</td>
            <td>${vehicle.plate}</td>
            <td>${vehicle.type}</td>
            <td>${vehicle.user_name || '-'}</td>
            <td>
                <button class="action-btn btn-delete" onclick="deleteVehicle('${vehicle.plate}')">删除</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// ==================== 用户管理 ====================

async function loadUsers() {
    try {
        console.log('开始加载用户数据...');
        const userType = document.getElementById('user-type-filter').value;

        const params = new URLSearchParams();
        if (userType) params.append('type', userType);

        const response = await fetch(`${API_BASE}/users?${params}`);
        const data = await response.json();

        console.log('用户数据响应:', data);

        if (data.success) {
            console.log('用户列表:', data.users);
            renderUsers(data.users);
        } else {
            console.error('获取用户数据失败:', data.message);
            showToast(data.message || '获取用户数据失败', 'error');
        }
    } catch (error) {
        console.error('加载用户数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

function renderUsers(users) {
    console.log('开始渲染用户列表，数量:', users.length);
    const tbody = document.getElementById('users-table-body');
    tbody.innerHTML = '';

    if (users.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td colspan="6" style="text-align: center; padding: 20px;">
                暂无用户数据
            </td>
        `;
        tbody.appendChild(tr);
        return;
    }

    users.forEach(user => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${user.id}</td>
            <td>${user.name}</td>
            <td>${user.type}</td>
            <td>${user.phone || '-'}</td>
            <td>${user.credit_score}</td>
            <td>
                <button class="action-btn btn-delete" onclick="deleteUser(${user.id})">删除</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 筛选按钮事件
document.getElementById('user-type-filter').addEventListener('change', loadUsers);

// ==================== 出入记录 ====================

async function loadRecords() {
    try {
        const [entryResponse, exitResponse] = await Promise.all([
            fetch(`${API_BASE}/records/entry`),
            fetch(`${API_BASE}/records/exit`)
        ]);

        const entryData = await entryResponse.json();
        const exitData = await exitResponse.json();

        if (entryData.success) {
            renderEntryRecords(entryData.records);
        }

        if (exitData.success) {
            renderExitRecords(exitData.records);
        }
    } catch (error) {
        console.error('加载记录数据失败:', error);
        showToast('加载数据失败', 'error');
    }
}

// 检查预约违约
async function checkReservationViolations() {
    try {
        const response = await fetch(`${API_BASE}/reservations/check-violations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const result = await response.json();
        if (result.success && result.message) {
            console.log(result.message);
        }
    } catch (error) {
        console.error('检查预约违约失败:', error);
    }
}

// 打开车辆入场弹窗
document.getElementById('vehicle-entry-btn').addEventListener('click', async () => {
    // 检查预约违约
    await checkReservationViolations();

    // 重置表单
    document.getElementById('entry-form').reset();
    // 隐藏预约字段和用户信息字段，显示无预约字段
    document.getElementById('reservation-fields').classList.add('hidden');
    document.getElementById('no-reservation-fields').classList.remove('hidden');
    document.getElementById('vehicle-info-fields').classList.add('hidden');
    document.getElementById('entry-modal').classList.remove('hidden');
});

// 关闭车辆入场弹窗
document.getElementById('entry-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('entry-modal').classList.add('hidden');
});

document.getElementById('entry-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('entry-modal').classList.add('hidden');
});

// 处理预约选择变化
document.getElementById('entry-has-reservation').addEventListener('change', (e) => {
    const hasReservation = e.target.value === 'true';
    const reservationFields = document.getElementById('reservation-fields');
    const noReservationFields = document.getElementById('no-reservation-fields');

    // 切换预约字段和无预约字段的显示
    if (hasReservation) {
        reservationFields.classList.remove('hidden');
        noReservationFields.classList.add('hidden');
        // 重置表单中的车辆类型、区域等字段
        document.getElementById('entry-vehicle-type').value = '';
        document.getElementById('entry-area').value = '';
        document.getElementById('entry-space-type').innerHTML = '<option value="">请先选择车辆类型</option>';
        document.getElementById('entry-space-number').innerHTML = '<option value="">请先选择区域和车位类型</option>';
    } else {
        reservationFields.classList.add('hidden');
        noReservationFields.classList.remove('hidden');
    }
});

// 加载空闲车位（入场登记模块）
async function loadEntryAvailableSpaces() {
    const vehicleType = document.getElementById('entry-vehicle-type').value;
    const area = document.getElementById('entry-area').value;
    const spaceType = document.getElementById('entry-space-type').value;
    const spaceNumberSelect = document.getElementById('entry-space-number');

    // 清空车位号选择框
    spaceNumberSelect.innerHTML = '<option value="">请选择车位号</option>';

    if (!vehicleType || !area || !spaceType) {
        return;
    }

    try {
        // 获取车位类型ID
        const typeResponse = await fetch(`${API_BASE}/parking/types`);
        const typeResult = await typeResponse.json();

        if (!typeResult.success) {
            throw new Error('获取车位类型失败');
        }

        const type = typeResult.types.find(t => t.name === spaceType);
        if (!type) {
            throw new Error('未找到对应的车位类型');
        }

        // 使用API端点获取空闲车位，传递车辆类型参数
        const response = await fetch(`${API_BASE}/parking/available?cl_type=${encodeURIComponent(vehicleType)}&area=${encodeURIComponent(area)}&type_id=${type.id}`);
        const result = await response.json();

        if (result.success && result.spaces.length > 0) {
            result.spaces.forEach(space => {
                const option = document.createElement('option');
                option.value = space.number;
                option.textContent = space.number;
                spaceNumberSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '该区域没有可用的车位';
            spaceNumberSelect.appendChild(option);
        }
    } catch (error) {
        console.error('加载空闲车位失败:', error);
        showToast('加载空闲车位失败', 'error');
    }
}

// 监听车辆类型变化，动态加载车位类型
document.getElementById('entry-vehicle-type').addEventListener('change', async (e) => {
    const vehicleType = e.target.value;
    const spaceTypeSelect = document.getElementById('entry-space-type');

    // 清空车位类型选择
    spaceTypeSelect.innerHTML = '<option value="">请选择车位类型</option>';

    if (!vehicleType) {
        spaceTypeSelect.innerHTML = '<option value="">请先选择车辆类型</option>';
        return;
    }

    // 根据车辆类型获取可用的车位类型
    const validTypeNames = getValidSpaceTypes(vehicleType);

    // 添加可用的车位类型选项
    validTypeNames.forEach(typeName => {
        const option = document.createElement('option');
        option.value = typeName;
        option.textContent = typeName;
        spaceTypeSelect.appendChild(option);
    });

    // 清空车位号选择
    document.getElementById('entry-space-number').innerHTML = '<option value="">请先选择区域和车位类型</option>';
});

// 监听区域和车位类型变化
document.getElementById('entry-area').addEventListener('change', loadEntryAvailableSpaces);
document.getElementById('entry-space-type').addEventListener('change', loadEntryAvailableSpaces);

// 处理车牌号输入，检查车辆是否存在
document.getElementById('entry-plate').addEventListener('blur', async (e) => {
    const plate = e.target.value.trim();
    const hasReservation = document.getElementById('entry-has-reservation').value === 'true';

    if (!plate || hasReservation) return;

    try {
        const response = await fetch(`${API_BASE}/vehicles/check/${plate}`);
        const result = await response.json();

        if (result.exists) {
            // 车辆存在，隐藏用户信息字段
            document.getElementById('vehicle-info-fields').classList.add('hidden');
        } else {
            // 车辆不存在，显示用户信息字段
            document.getElementById('vehicle-info-fields').classList.remove('hidden');
        }
    } catch (error) {
        console.error('检查车辆失败:', error);
    }
});

// 提交车辆入场表单
document.getElementById('entry-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const plate = document.getElementById('entry-plate').value.trim();
    const gate = document.getElementById('entry-gate').value;
    const has_reservation = document.getElementById('entry-has-reservation').value === 'true';

    // 验证必填字段
    if (!plate || !gate) {
        showToast('请填写所有必填字段', 'error');
        return;
    }

    const data = {
        plate,
        gate,
        has_reservation
    };

    // 如果有预约，添加预约码
    if (has_reservation) {
        const reservation_code = document.getElementById('entry-reservation-code').value;
        if (!reservation_code) {
            showToast('请输入预约码', 'error');
            return;
        }
        data.reservation_code = parseInt(reservation_code);
    } else {
        // 如果没有预约，检查车辆是否存在
        try {
            const response = await fetch(`${API_BASE}/vehicles/check/${plate}`);
            const result = await response.json();

            if (!result.exists) {
                // 车辆不存在，添加用户信息
                const user_name = document.getElementById('entry-user-name').value.trim();
                const user_phone = document.getElementById('entry-user-phone').value.trim();

                if (!user_name || !user_phone) {
                    showToast('请填写用户姓名和电话号码', 'error');
                    return;
                }

                data.user_name = user_name;
                data.user_phone = user_phone;
            }
        } catch (error) {
            console.error('检查车辆失败:', error);
        }

        // 添加车辆类型、区域、车位类型和车位号
        const vehicle_type = document.getElementById('entry-vehicle-type').value;
        const area = document.getElementById('entry-area').value;
        const space_type = document.getElementById('entry-space-type').value;
        const space_number = document.getElementById('entry-space-number').value.trim();

        if (!vehicle_type || !area || !space_type || !space_number) {
            showToast('请选择车辆类型、区域、车位类型并输入车位号', 'error');
            return;
        }

        data.vehicle_type = vehicle_type;
        data.area = area;
        data.space_type = space_type;
        data.space_number = space_number;
    }

    try {
        const response = await fetch(`${API_BASE}/records/entry`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showToast('车辆入场成功', 'success');
            document.getElementById('entry-modal').classList.add('hidden');
            await loadRecords();
        } else {
            showToast(result.message || '车辆入场失败', 'error');
        }
    } catch (error) {
        console.error('车辆入场失败:', error);
        showToast('车辆入场失败', 'error');
    }
});

// 打开车辆出场弹窗
document.getElementById('vehicle-exit-btn').addEventListener('click', () => {
    // 重置表单
    document.getElementById('exit-form').reset();
    document.getElementById('exit-modal').classList.remove('hidden');
});

// 关闭车辆出场弹窗
document.getElementById('exit-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('exit-modal').classList.add('hidden');
});

document.getElementById('exit-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('exit-modal').classList.add('hidden');
});

// 提交车辆出场表单
document.getElementById('exit-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const plate = document.getElementById('exit-plate').value.trim();
    const gate = document.getElementById('exit-gate').value;

    // 验证必填字段
    if (!plate || !gate) {
        showToast('请填写所有必填字段', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/records/exit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plate,
                gate
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('车辆出场成功', 'success');
            document.getElementById('exit-modal').classList.add('hidden');
            await loadRecords();
        } else {
            showToast(data.message || '车辆出场失败', 'error');
        }
    } catch (error) {
        console.error('车辆出场失败:', error);
        showToast('车辆出场失败', 'error');
    }
});

// 处理出场操作（从入场记录点击出场按钮）
async function handleExit(plate) {
    // 设置车牌号
    document.getElementById('exit-plate').value = plate;
    // 打开出场弹窗
    document.getElementById('exit-modal').classList.remove('hidden');
}

function renderEntryRecords(records) {
    const tbody = document.getElementById('entry-records-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    records.forEach(record => {
        const tr = document.createElement('tr');
        const statusClass = record.is_exited ? 'exited' : 'parking';
        const statusText = record.is_exited ? '已出场' : '停车中';
        const exitButton = record.is_exited 
            ? '<span class="status-badge exited">已出场</span>'
            : `<button class="action-btn btn-exit" onclick="handleExit('${record.plate}')">出场</button>`;

        tr.innerHTML = `
            <td>${record.id}</td>
            <td>${record.plate}</td>
            <td>${record.time}</td>
            <td>${record.gate || '-'}</td>
            <td>${record.space_number || '-'}</td>
            <td>${record.reservation_id || '-'}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>${exitButton}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderExitRecords(records) {
    const tbody = document.getElementById('exit-records-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    records.forEach(record => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${record.id}</td>
            <td>${record.plate}</td>
            <td>${record.time}</td>
            <td>${record.gate || '-'}</td>
            <td>${record.parking_hours || '-'}</td>
            <td>${record.parking_fee || '-'}</td>
            <td><span class="status-badge ${record.pay_status}">${record.pay_status}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// ==================== 车辆管理 - 新建和删除 ====================

// 打开新建车辆弹窗
document.getElementById('add-vehicle-btn').addEventListener('click', async () => {
    // 加载用户列表
    await loadUsersForVehicle();
    document.getElementById('vehicle-form').reset();
    document.getElementById('vehicle-modal').classList.remove('hidden');
});

// 关闭车辆弹窗
document.getElementById('vehicle-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('vehicle-modal').classList.add('hidden');
});

document.getElementById('vehicle-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('vehicle-modal').classList.add('hidden');
});

// 加载用户列表（用于车辆表单）
async function loadUsersForVehicle() {
    try {
        const response = await fetch(`${API_BASE}/users`);
        const data = await response.json();

        if (data.success) {
            const userSelect = document.getElementById('vehicle-user');
            userSelect.innerHTML = '<option value="">公共车辆（不选）</option>';
            data.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = `${user.name} (${user.type})`;
                option.setAttribute('data-type', user.type);
                userSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载用户列表失败:', error);
        showToast('加载用户列表失败', 'error');
    }
}

// 所属用户改变时的事件监听器
document.getElementById('vehicle-user').addEventListener('change', function() {
    const userId = this.value;
    const typeSelect = document.getElementById('vehicle-type');

    if (userId) {
        // 获取用户信息
        const userOption = this.options[this.selectedIndex];
        const userType = userOption.getAttribute('data-type');

        // 自动设置车辆类型为用户类型
        if (userType && (userType === '教职工' || userType === '学生' || userType === '访客')) {
            typeSelect.value = userType;
            // 禁用车辆类型选择框，防止用户手动修改
            typeSelect.disabled = true;
        }
    } else {
        // 如果没有选择用户，启用车辆类型选择框并清空选择
        typeSelect.disabled = false;
        typeSelect.value = '';
    }
});

// 车辆类型改变时的事件监听器
document.getElementById('vehicle-type').addEventListener('change', function() {
    const type = this.value;
    const userSelect = document.getElementById('vehicle-user');

    if (type === '公务车辆' || type === '特殊车辆') {
        // 禁用用户选择并清空选择
        userSelect.disabled = true;
        userSelect.value = '';
    } else {
        // 启用用户选择
        userSelect.disabled = false;
    }
});

// 提交新建车辆表单
document.getElementById('vehicle-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const plate = document.getElementById('vehicle-plate').value.trim();
    const type = document.getElementById('vehicle-type').value;
    const userId = document.getElementById('vehicle-user').value;

    // 验证：公务车辆和特殊车辆不能选择所属用户
    if ((type === '公务车辆' || type === '特殊车辆') && userId) {
        showToast('公务车辆和特殊车辆不能选择所属用户', 'error');
        return;
    }

    // 验证：教职工、学生、访客车辆必须选择所属用户
    if ((type === '教职工' || type === '学生' || type === '访客') && !userId) {
        showToast('教职工、学生、访客车辆必须选择所属用户', 'error');
        return;
    }

    // 验证：车辆类型和用户类型必须一致
    if (userId) {
        const userSelect = document.getElementById('vehicle-user');
        const userOption = userSelect.options[userSelect.selectedIndex];
        const userType = userOption.getAttribute('data-type');

        if (userType && userType !== type) {
            showToast(`车辆类型（${type}）与用户类型（${userType}）不一致`, 'error');
            return;
        }
    }

    try {
        const response = await fetch(`${API_BASE}/vehicles`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plate: plate,
                type: type,
                user_id: userId ? parseInt(userId) : null
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('车辆创建成功', 'success');
            document.getElementById('vehicle-modal').classList.add('hidden');
            await loadVehiclesManagement();
        } else {
            showToast(data.message || '车辆创建失败', 'error');
        }
    } catch (error) {
        console.error('创建车辆失败:', error);
        showToast('创建车辆失败', 'error');
    }
});

// 删除车辆
async function deleteVehicle(plate) {
    if (!confirm(`确定要删除车牌号为 ${plate} 的车辆吗？`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/vehicles/${plate}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('车辆删除成功', 'success');
            await loadVehiclesManagement();
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    } catch (error) {
        console.error('删除车辆失败:', error);
        showToast('删除失败', 'error');
    }
}

// 刷新车辆列表
document.getElementById('refresh-vehicles').addEventListener('click', loadVehiclesManagement);

// ==================== 用户管理 - 新建和删除 ====================

// 打开新建用户弹窗
document.getElementById('add-user-btn').addEventListener('click', () => {
    document.getElementById('user-form').reset();
    document.getElementById('user-modal').classList.remove('hidden');
});

// 关闭用户弹窗
document.getElementById('user-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('user-modal').classList.add('hidden');
});

document.getElementById('user-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('user-modal').classList.add('hidden');
});

// 提交新建用户表单
document.getElementById('user-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const userId = parseInt(document.getElementById('user-id').value);
    const name = document.getElementById('user-name').value.trim();
    const type = document.getElementById('user-type').value;
    const phone = document.getElementById('user-phone').value.trim();
    const creditScore = parseInt(document.getElementById('user-credit').value) || 100;

    if (!userId) {
        showToast('请输入用户ID', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                name: name,
                type: type,
                phone: phone || null,
                credit_score: creditScore
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('用户创建成功', 'success');
            document.getElementById('user-modal').classList.add('hidden');
            await loadUsers();
        } else {
            showToast(data.message || '用户创建失败', 'error');
        }
    } catch (error) {
        console.error('创建用户失败:', error);
        showToast('创建用户失败', 'error');
    }
});

// ==================== 批量导入功能 ====================

// 打开批量导入用户弹窗
document.getElementById('import-users-btn').addEventListener('click', () => {
    document.getElementById('import-users-modal').classList.remove('hidden');
    document.getElementById('import-users-file').value = '';
});

// 关闭批量导入用户弹窗
document.getElementById('import-users-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('import-users-modal').classList.add('hidden');
});

document.getElementById('import-users-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('import-users-modal').classList.add('hidden');
});

// 提交批量导入用户
document.getElementById('import-users-submit').addEventListener('click', async () => {
    const fileInput = document.getElementById('import-users-file');
    const file = fileInput.files[0];

    if (!file) {
        showToast('请选择CSV文件', 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
        const content = e.target.result;
        const lines = content.split('\n');
        const users = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            const parts = line.split(',');
            if (parts.length < 3) {
                showToast(`第${i + 1}行数据格式错误，请检查`, 'error');
                return;
            }

            users.push({
                user_id: parts[0].trim(),
                user_name: parts[1].trim(),
                user_type: parts[2].trim(),
                user_phone: parts[3] ? parts[3].trim() : '',
                credit_score: parts[4] ? parseInt(parts[4].trim()) : 100
            });
        }

        try {
            const response = await fetch(`${API_BASE}/users/batch-import`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ users })
            });

            const data = await response.json();

            if (data.success) {
                showToast(`成功导入${data.success_count}个用户`, 'success');
                document.getElementById('import-users-modal').classList.add('hidden');
                await loadUsers();
            } else {
                showToast(data.message || '导入失败', 'error');
            }
        } catch (error) {
            console.error('批量导入用户失败:', error);
            showToast('批量导入用户失败', 'error');
        }
    };

    reader.readAsText(file);
});

// 打开批量导入车辆弹窗
document.getElementById('import-vehicles-btn').addEventListener('click', () => {
    document.getElementById('import-vehicles-modal').classList.remove('hidden');
    document.getElementById('import-vehicles-file').value = '';
});

// 关闭批量导入车辆弹窗
document.getElementById('import-vehicles-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('import-vehicles-modal').classList.add('hidden');
});

document.getElementById('import-vehicles-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('import-vehicles-modal').classList.add('hidden');
});

// 提交批量导入车辆
document.getElementById('import-vehicles-submit').addEventListener('click', async () => {
    const fileInput = document.getElementById('import-vehicles-file');
    const file = fileInput.files[0];

    if (!file) {
        showToast('请选择CSV文件', 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
        const content = e.target.result;
        const lines = content.split('\n');
        const vehicles = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            const parts = line.split(',');
            if (parts.length < 2) {
                showToast(`第${i + 1}行数据格式错误，请检查`, 'error');
                return;
            }

            vehicles.push({
                plate: parts[0].trim(),
                vehicle_type: parts[1].trim(),
                user_id: parts[2] ? parseInt(parts[2].trim()) : null
            });
        }

        try {
            const response = await fetch(`${API_BASE}/vehicles/batch-import`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ vehicles })
            });

            const data = await response.json();

            if (data.success) {
                showToast(`成功导入${data.success_count}个车辆`, 'success');
                document.getElementById('import-vehicles-modal').classList.add('hidden');
                await loadVehiclesManagement();
            } else {
                showToast(data.message || '导入失败', 'error');
            }
        } catch (error) {
            console.error('批量导入车辆失败:', error);
            showToast('批量导入车辆失败', 'error');
        }
    };

    reader.readAsText(file);
});

// 删除用户
async function deleteUser(userId) {
    if (!confirm(`确定要删除ID为 ${userId} 的用户吗？`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('用户删除成功', 'success');
            await loadUsers();
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    } catch (error) {
        console.error('删除用户失败:', error);
        showToast('删除失败', 'error');
    }
}

// ==================== 支付功能 ====================

// 打开支付弹窗
function openPaymentModal(outId) {
    // 获取支付记录详情
    fetch(`${API_BASE}/payment/status/${outId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 填充支付信息
                document.getElementById('payment-plate').textContent = data.plate;
                document.getElementById('payment-in-time').textContent = data.in_time;
                document.getElementById('payment-out-time').textContent = data.out_time;
                document.getElementById('payment-hours').textContent = data.parking_hours + ' 小时';
                document.getElementById('payment-fee').textContent = data.parking_fee + ' 元';
                
                // 存储outId到按钮的data属性中
                document.getElementById('confirm-payment-btn').dataset.outId = outId;
                
                // 显示支付弹窗
                document.getElementById('payment-modal').classList.remove('hidden');
            } else {
                showToast(data.message || '获取支付信息失败', 'error');
            }
        })
        .catch(error => {
            console.error('获取支付信息失败:', error);
            showToast('获取支付信息失败', 'error');
        });
}

// 关闭支付弹窗
document.getElementById('payment-modal').querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('payment-modal').classList.add('hidden');
});

document.getElementById('payment-modal').querySelector('.modal-cancel').addEventListener('click', () => {
    document.getElementById('payment-modal').classList.add('hidden');
});

// 确认支付
document.getElementById('confirm-payment-btn').addEventListener('click', async () => {
    const outId = document.getElementById('confirm-payment-btn').dataset.outId;
    const paymentMethod = document.getElementById('payment-method').value;
    
    if (!outId) {
        showToast('缺少出场记录ID', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/payment/pay`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                out_id: outId,
                payment_method: paymentMethod
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`支付成功，金额: ${data.fee} 元`, 'success');
            document.getElementById('payment-modal').classList.add('hidden');
            await loadRecords(); // 刷新记录列表
        } else {
            showToast(data.message || '支付失败', 'error');
        }
    } catch (error) {
        console.error('支付失败:', error);
        showToast('支付失败', 'error');
    }
});

// 查看未支付记录
document.getElementById('unpaid-records-btn').addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_BASE}/payment/unpaid`);
        const data = await response.json();
        
        if (data.success) {
            // 切换到出场记录标签页
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector('.tab-btn[data-tab="exit"]').classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById('exit-tab').classList.add('active');
            
            // 渲染未支付记录
            renderUnpaidRecords(data.records);
        } else {
            showToast(data.message || '获取未支付记录失败', 'error');
        }
    } catch (error) {
        console.error('获取未支付记录失败:', error);
        showToast('获取未支付记录失败', 'error');
    }
});

// 渲染未支付记录
function renderUnpaidRecords(records) {
    const tbody = document.getElementById('exit-records-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="no-data">暂无未支付记录</td></tr>';
        return;
    }
    
    records.forEach(record => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${record.out_id}</td>
            <td>${record.plate}</td>
            <td>${record.out_time}</td>
            <td>-</td>
            <td>${record.parking_hours} 小时</td>
            <td>${record.parking_fee} 元</td>
            <td><span class="status-badge 未支付">未支付</span></td>
            <td>
                <button class="action-btn btn-pay" onclick="openPaymentModal(${record.out_id})">支付</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 修改renderExitRecords函数，添加支付按钮
const originalRenderExitRecords = renderExitRecords;
renderExitRecords = function(records) {
    const tbody = document.getElementById('exit-records-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    records.forEach(record => {
        const tr = document.createElement('tr');
        
        // 根据支付状态显示不同的操作按钮
        let actionButton = '';
        if (record.pay_status === '未支付') {
            actionButton = `<button class="action-btn btn-pay" onclick="openPaymentModal(${record.id})">支付</button>`;
        } else if (record.pay_status === '已支付') {
            actionButton = '<span class="status-badge 已支付">已支付</span>';
        } else if (record.pay_status === '免费') {
            actionButton = '<span class="status-badge 免费">免费</span>';
        } else {
            actionButton = '<span class="status-badge 异常">异常</span>';
        }
        
        tr.innerHTML = `
            <td>${record.id}</td>
            <td>${record.plate}</td>
            <td>${record.time}</td>
            <td>${record.gate || '-'}</td>
            <td>${record.parking_hours || '-'}</td>
            <td>${record.parking_fee || '-'}</td>
            <td><span class="status-badge ${record.pay_status}">${record.pay_status}</span></td>
            <td>${actionButton}</td>
        `;
        tbody.appendChild(tr);
    });
};

// 刷新用户列表
document.getElementById('refresh-users').addEventListener('click', loadUsers);
