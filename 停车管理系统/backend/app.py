from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pyodbc
from datetime import datetime, timedelta
import hashlib
import os

app = Flask(__name__, static_folder='../frontend')
CORS(app)

# 数据库配置
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'fjutspace',
    'trusted_connection': 'yes'
}

def get_db_connection():
    """获取数据库连接"""
    conn = pyodbc.connect(
        'DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection={trusted_connection}'.format(**DB_CONFIG)
    )
    return conn

# ==================== 静态文件服务 ====================

@app.route('/')
def index():
    """返回前端主页"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """返回静态文件"""
    return send_from_directory(app.static_folder, path)

# ==================== 认证相关接口 ====================

@app.route('/api/login', methods=['POST'])
def login():
    """管理员登录"""
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT UserID, UserName, UserType 
            FROM FjutUser 
            WHERE UserName = ?
        """, (username,))

        user = cursor.fetchone()

        if user:
            return jsonify({
                'success': True,
                'user': {
                    'id': user[0],
                    'name': user[1],
                    'type': user[2]
                }
            })
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    finally:
        conn.close()

# ==================== 车位管理相关接口 ====================

@app.route('/api/parking/stats', methods=['GET'])
def get_parking_stats():
    """获取车位统计信息"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 获取区域统计
        cursor.execute("SELECT * FROM vw_AreaParkingStats")
        area_stats = []
        for row in cursor.fetchall():
            area_stats.append({
                'area': row[0],
                'total': row[1],
                'available': row[2],
                'occupied': row[3],
                'reserved': row[4],
                'maintenance': row[5]
            })

        # 获取类型统计
        cursor.execute("SELECT * FROM vw_TypeAvailableStats")
        type_stats = []
        for row in cursor.fetchall():
            type_stats.append({
                'type_id': row[0],
                'type_name': row[1],
                'total': row[2],
                'available': row[3],
                'occupied': row[4],
                'reserved': row[5],
                'maintenance': row[6]
            })

        return jsonify({
            'success': True,
            'area_stats': area_stats,
            'type_stats': type_stats
        })
    finally:
        conn.close()

@app.route('/api/parking/spaces', methods=['GET'])
def get_parking_spaces():
    """获取车位列表"""
    area = request.args.get('area')
    type_id = request.args.get('type_id')
    status = request.args.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT cw.CwID, cw.Cwbh, cw.Area, cw.Status, 
                   ct.TypeName, ct.TypeID
            FROM Cwgl cw
            INNER JOIN CwType ct ON cw.TypeID = ct.TypeID
            WHERE 1=1
        """
        params = []

        if area:
            query += " AND cw.Area = ?"
            params.append(area)

        if type_id:
            query += " AND ct.TypeID = ?"
            params.append(type_id)

        if status:
            query += " AND cw.Status = ?"
            params.append(status)

        cursor.execute(query, params)

        spaces = []
        for row in cursor.fetchall():
            spaces.append({
                'id': row[0],
                'number': row[1],
                'area': row[2],
                'status': row[3],
                'type_name': row[4],
                'type_id': row[5]
            })

        return jsonify({'success': True, 'spaces': spaces})
    finally:
        conn.close()

@app.route('/api/parking/space/<int:space_id>', methods=['PUT'])
def update_parking_space(space_id):
    """更新车位状态"""
    data = request.json
    status = data.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE Cwgl 
            SET Status = ? 
            WHERE CwID = ?
        """, (status, space_id))

        conn.commit()
        return jsonify({'success': True, 'message': '车位状态更新成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# ==================== 预约管理相关接口 ====================

@app.route('/api/reservations', methods=['GET'])
def get_reservations():
    """获取预约列表"""
    status = request.args.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT pr.ReservationID, pr.UserID, fu.UserName, fu.UserType,
                   pr.CphID, cl.ClType, pr.CwID, cw.Cwbh, cw.Area,
                   ct.TypeName, pr.StartTime, pr.EndTime, 
                   pr.Purpose, pr.Status
            FROM ParkingReservations pr
            LEFT JOIN FjutUser fu ON pr.UserID = fu.UserID
            LEFT JOIN Clgl cl ON pr.CphID = cl.CphID
            LEFT JOIN Cwgl cw ON pr.CwID = cw.CwID
            LEFT JOIN CwType ct ON pr.TypeID = ct.TypeID
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND pr.Status = ?"
            params.append(status)

        query += " ORDER BY pr.StartTime DESC"

        cursor.execute(query, params)

        reservations = []
        for row in cursor.fetchall():
            reservations.append({
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2] if row[2] else '公共车辆',
                'user_type': row[3] if row[3] else '公共',
                'plate': row[4] if row[4] else '未知',
                'vehicle_type': row[5] if row[5] else '未知',
                'space_id': row[6],
                'space_number': row[7] if row[7] else '未知',
                'area': row[8] if row[8] else '未知',
                'space_type': row[9] if row[9] else '未知',
                'start_time': row[10].strftime('%Y-%m-%d %H:%M:%S') if row[10] else None,
                'end_time': row[11].strftime('%Y-%m-%d %H:%M:%S') if row[11] else None,
                'purpose': row[12] if row[12] else '',
                'status': row[13]
            })

        return jsonify({'success': True, 'reservations': reservations})
    finally:
        conn.close()

@app.route('/api/reservations', methods=['POST'])
def create_reservation():
    """新建预约，调用存储过程 proc_CreateParkingReservation"""
    from datetime import datetime

    data = request.json
    user_id = data.get('user_id')
    cw_id = data.get('cw_id')
    cph_id = data.get('cph_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    purpose = data.get('purpose', '')

    # 转换日期时间格式
    print(f"原始开始时间: {start_time}, 原始结束时间: {end_time}")
    try:
        if start_time:
            # 处理datetime-local格式 (YYYY-MM-DDTHH:mm)
            if 'T' in start_time:
                start_time = datetime.fromisoformat(start_time)
            else:
                # 处理其他格式
                start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            print(f"解析后的开始时间: {start_time}, 类型: {type(start_time)}")
        if end_time:
            # 处理datetime-local格式 (YYYY-MM-DDTHH:mm)
            if 'T' in end_time:
                end_time = datetime.fromisoformat(end_time)
            else:
                # 处理其他格式
                end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            print(f"解析后的结束时间: {end_time}, 类型: {type(end_time)}")
    except ValueError as e:
        print(f"日期时间解析错误: {str(e)}")
        return jsonify({'success': False, 'message': f'日期时间格式错误: {str(e)}'})

    # 验证必填字段
    if not all([cw_id, cph_id, start_time, end_time]):
        return jsonify({'success': False, 'message': '请填写所有必填项'})

    # 如果没有提供user_id，则必须选择公务车辆或特殊车辆
    if not user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT ClType FROM Clgl WHERE CphID = ?", (cph_id,))
            result = cursor.fetchone()
            if not result or result[0] not in ['公务车辆', '特殊车辆']:
                return jsonify({'success': False, 'message': '未选择用户时只能选择公务车辆或特殊车辆'})
        finally:
            conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 调用存储过程创建预约
        # 使用SET NOCOUNT ON来避免影响输出参数的获取
        cursor.execute("SET NOCOUNT ON")

        # 调用存储过程
        cursor.execute("""
            DECLARE @ReservationID INT
            EXEC proc_CreateParkingReservation
                @UserID = ?,
                @CphID = ?,
                @CwID = ?,
                @StartTime = ?,
                @EndTime = ?,
                @Purpose = ?,
                @ReservationID = @ReservationID OUTPUT
            SELECT @ReservationID AS ReservationID
        """, (user_id, cph_id, cw_id, start_time, end_time, purpose))

        # 获取返回的ReservationID
        row = cursor.fetchone()
        if row:
            reservation_id = row[0]
        else:
            reservation_id = None

        conn.commit()
        return jsonify({'success': True, 'message': '预约创建成功', 'reservation_id': reservation_id})
    except pyodbc.Error as e:
        conn.rollback()
        error_msg = str(e)
        # 提取存储过程中的错误消息
        if 'RAISERROR' in error_msg:
            error_msg = error_msg.split('RAISERROR')[-1].strip()
        return jsonify({'success': False, 'message': error_msg})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/reservations/<int:reservation_id>/approve', methods=['POST'])
def approve_reservation(reservation_id):
    """审批预约，调用存储过程 proc_ApproveReservation"""
    data = request.json
    approve = data.get('approve', True)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 调用存储过程审批预约
        cursor.execute("""
            EXEC proc_ApproveReservation
                @ReservationID = ?,
                @Approve = ?
        """, (reservation_id, 1 if approve else 0))

        conn.commit()
        return jsonify({'success': True, 'message': '预约处理成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/reservations/<int:reservation_id>/cancel', methods=['POST'])
def cancel_reservation(reservation_id):
    """取消预约，调用存储过程 proc_CancelReservation"""
    data = request.json
    user_id = data.get('user_id')
    reason = data.get('reason', '')

    print(f"取消预约 - ReservationID: {reservation_id}, UserID: {user_id}, Type: {type(user_id)}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 调用存储过程取消预约
        cursor.execute("""
            EXEC proc_CancelReservation
                @ReservationID = ?,
                @UserID = ?,
                @Reason = ?
        """, (reservation_id, user_id, reason))

        conn.commit()
        return jsonify({'success': True, 'message': '预约已取消'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/reservations/user/<int:user_id>', methods=['GET'])
def get_user_reservations(user_id):
    """获取指定用户的预约记录"""
    status = request.args.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            EXEC proc_GetUserReservations
                @UserID = ?,
                @Status = ?
        """, (user_id, status if status else None))

        reservations = []
        for row in cursor.fetchall():
            reservations.append({
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'plate': row[3],
                'vehicle_type': row[4],
                'space_id': row[5],
                'space_number': row[6],
                'area': row[7],
                'space_type': row[8],
                'start_time': row[9].strftime('%Y-%m-%d %H:%M:%S') if row[9] else None,
                'end_time': row[10].strftime('%Y-%m-%d %H:%M:%S') if row[10] else None,
                'purpose': row[11],
                'status': row[12]
            })

        return jsonify({'success': True, 'reservations': reservations})
    finally:
        conn.close()

# ==================== 车辆管理相关接口 ====================

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    """获取车辆列表"""
    user_id = request.args.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if user_id:
            # 获取指定用户的车辆
            cursor.execute("""
                SELECT c.CphID, c.ClType, c.UserID, fu.UserName
                FROM Clgl c
                LEFT JOIN FjutUser fu ON c.UserID = fu.UserID
                WHERE c.UserID = ?
                ORDER BY c.CphID
            """, (user_id,))
        else:
            # 获取所有车辆
            cursor.execute("""
                SELECT c.CphID, c.ClType, c.UserID, fu.UserName
                FROM Clgl c
                LEFT JOIN FjutUser fu ON c.UserID = fu.UserID
                ORDER BY c.ClType, c.CphID
            """)

        vehicles = []
        for row in cursor.fetchall():
            vehicles.append({
                'id': row[0],  # CphID作为ID
                'plate': row[0],  # CphID
                'type': row[1],
                'user_id': row[2],
                'user_name': row[3] if row[3] else '公共车辆'
            })

        return jsonify({'success': True, 'vehicles': vehicles})
    finally:
        conn.close()

@app.route('/api/vehicles/user/<int:user_id>', methods=['GET'])
def get_user_vehicles(user_id):
    """获取指定用户的车辆"""
    print(f"获取用户 {user_id} 的车辆")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            EXEC proc_GetUserVehicles @UserID = ?
        """, (user_id,))

        vehicles = []
        for row in cursor.fetchall():
            print(f"找到车辆: {row[0]}, 类型: {row[1]}")
            vehicles.append({
                'id': row[0],  # CphID作为ID
                'plate': row[0],  # CphID
                'type': row[1],
                'user_id': row[2],
                'owner_name': row[3]
            })

        print(f"总共找到 {len(vehicles)} 辆车")
        return jsonify({'success': True, 'vehicles': vehicles})
    except Exception as e:
        print(f"获取用户车辆时出错: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/vehicles/public', methods=['GET'])
def get_public_vehicles():
    """获取公共车辆（公务车辆和特殊车辆）"""
    print("获取公共车辆")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            EXEC proc_GetUserVehicles @UserID = NULL
        """)

        vehicles = []
        for row in cursor.fetchall():
            print(f"找到公共车辆: {row[0]}, 类型: {row[1]}")
            vehicles.append({
                'id': row[0],  # CphID作为ID
                'plate': row[0],  # CphID
                'type': row[1],
                'user_id': row[2],
                'owner_name': row[3]
            })

        print(f"总共找到 {len(vehicles)} 辆公共车辆")
        return jsonify({'success': True, 'vehicles': vehicles})
    except Exception as e:
        print(f"获取公共车辆时出错: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/vehicles', methods=['POST'])
def create_vehicle():
    """新建车辆"""
    data = request.json
    plate = data.get('plate')
    cl_type = data.get('type')
    user_id = data.get('user_id')

    if not plate or not cl_type:
        return jsonify({'success': False, 'message': '车牌号和车辆类型为必填项'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 检查车牌号是否已存在
        cursor.execute("SELECT COUNT(*) FROM Clgl WHERE CphID = ?", (plate,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': '该车牌号已存在'})

        # 插入新车辆
        cursor.execute("""
            INSERT INTO Clgl (CphID, ClType, UserID)
            VALUES (?, ?, ?)
        """, (plate, cl_type, user_id if user_id else None))

        conn.commit()
        return jsonify({'success': True, 'message': '车辆创建成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/vehicles/<string:plate>', methods=['DELETE'])
def delete_vehicle(plate):
    """删除车辆"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 检查车辆是否存在
        cursor.execute("SELECT COUNT(*) FROM Clgl WHERE CphID = ?", (plate,))
        if cursor.fetchone()[0] == 0:
            return jsonify({'success': False, 'message': '车辆不存在'})

        # 检查车辆是否有未完成的预约
        cursor.execute("""
            SELECT COUNT(*) FROM ParkingReservations
            WHERE CphID = ? AND Status IN ('待审批', '已批准')
        """, (plate,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': '该车辆有未完成的预约，无法删除'})

        # 检查车辆是否有未完成的入场记录
        cursor.execute("""
            SELECT COUNT(*) FROM InSpace
            WHERE CphID = ? AND InID NOT IN (SELECT InID FROM OutSpace)
        """, (plate,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': '该车辆有未完成的入场记录，无法删除'})

        # 由于InSpace表有外键约束，需要先删除相关的入场记录
        # 获取所有相关的InID
        cursor.execute("""
            SELECT InID FROM InSpace WHERE CphID = ?
        """, (plate,))
        in_ids = [row[0] for row in cursor.fetchall()]

        # 先删除OutSpace记录
        if in_ids:
            placeholders = ','.join(['?' for _ in in_ids])
            cursor.execute(f"""
                DELETE FROM OutSpace WHERE InID IN ({placeholders})
            """, in_ids)

        # 再删除InSpace记录
        cursor.execute("DELETE FROM InSpace WHERE CphID = ?", (plate,))

        # 删除车辆
        cursor.execute("DELETE FROM Clgl WHERE CphID = ?", (plate,))
        conn.commit()
        return jsonify({'success': True, 'message': '车辆删除成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/parking/available', methods=['GET'])
def get_available_spaces():
    """获取可用车位"""
    cl_type = request.args.get('cl_type')
    area = request.args.get('area')
    type_id = request.args.get('type_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            EXEC proc_GetAvailableSpaces
                @ClType = ?,
                @Area = ?,
                @TypeID = ?
        """, (cl_type, area, type_id if type_id else None))

        spaces = []
        for row in cursor.fetchall():
            spaces.append({
                'id': row[0],
                'number': row[1],
                'area': row[2],
                'status': row[3],
                'type_id': row[4],
                'type_name': row[5]
            })

        return jsonify({'success': True, 'spaces': spaces})
    finally:
        conn.close()

# ==================== 用户管理相关接口 ====================

@app.route('/api/users', methods=['GET'])
def get_users():
    """获取用户列表"""
    user_type = request.args.get('type')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT UserID, UserName, UserType, UserPhone, CreditScore
            FROM FjutUser
            WHERE 1=1
        """
        params = []

        if user_type:
            query += " AND UserType = ?"
            params.append(user_type)

        cursor.execute(query, params)

        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'phone': row[3],
                'credit_score': row[4]
            })

        return jsonify({'success': True, 'users': users})
    finally:
        conn.close()

@app.route('/api/users', methods=['POST'])
def create_user():
    """新建用户"""
    data = request.json
    user_id = data.get('user_id')
    name = data.get('name')
    user_type = data.get('type')
    phone = data.get('phone')
    credit_score = data.get('credit_score', 100)

    if not user_id or not name or not user_type:
        return jsonify({'success': False, 'message': '用户ID、用户名和用户类型为必填项'})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 检查用户ID是否已存在
        cursor.execute("SELECT COUNT(*) FROM FjutUser WHERE UserID = ?", (user_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': '该用户ID已存在'})

        # 插入新用户
        cursor.execute("""
            INSERT INTO FjutUser (UserID, UserName, UserType, UserPhone, CreditScore)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, user_type, phone, credit_score))

        conn.commit()
        return jsonify({'success': True, 'message': '用户创建成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """删除用户"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 检查用户是否存在
        cursor.execute("SELECT COUNT(*) FROM FjutUser WHERE UserID = ?", (user_id,))
        if cursor.fetchone()[0] == 0:
            return jsonify({'success': False, 'message': '用户不存在'})

        # 检查用户是否有未完成的预约
        cursor.execute("""
            SELECT COUNT(*) FROM ParkingReservations
            WHERE UserID = ? AND Status IN ('待审批', '已批准')
        """, (user_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': '该用户有未完成的预约，无法删除'})

        # 检查用户是否有关联的车辆
        cursor.execute("SELECT COUNT(*) FROM Clgl WHERE UserID = ?", (user_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': '该用户有关联的车辆，无法删除'})

        # 删除用户
        cursor.execute("DELETE FROM FjutUser WHERE UserID = ?", (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '用户删除成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# ==================== 入场出场记录相关接口 ====================

@app.route('/api/vehicles/check/<plate>', methods=['GET'])
def check_vehicle(plate):
    """检查车辆是否存在"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM Clgl WHERE CphID = ?", (plate,))
        count = cursor.fetchone()[0]
        return jsonify({'exists': count > 0})
    finally:
        conn.close()

@app.route('/api/records/entry', methods=['GET', 'POST'])
def handle_entry_records():
    """处理入场记录（获取或创建）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        """获取入场记录"""
        try:
            cursor.execute("""
                SELECT i.InID, i.CphID, i.InTime, i.InGate, i.CwID, cw.Cwbh, i.ReservationID,
                       CASE WHEN o.OutID IS NOT NULL THEN 1 ELSE 0 END as is_exited
                FROM InSpace i
                LEFT JOIN Cwgl cw ON i.CwID = cw.CwID
                LEFT JOIN OutSpace o ON i.InID = o.InID
                ORDER BY i.InTime DESC
            """)

            records = []
            for row in cursor.fetchall():
                records.append({
                    'id': row[0],
                    'plate': row[1],
                    'time': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None,
                    'gate': row[3],
                    'space_id': row[4],
                    'space_number': row[5],
                    'reservation_id': row[6],
                    'is_exited': bool(row[7])
                })

            return jsonify({'success': True, 'records': records})
        finally:
            conn.close()

    elif request.method == 'POST':
        """创建入场记录"""
        data = request.json
        plate = data.get('plate')
        gate = data.get('gate')
        has_reservation = data.get('has_reservation', False)
        reservation_code = data.get('reservation_code')
        user_name = data.get('user_name')
        user_phone = data.get('user_phone')
        area = data.get('area')
        space_type = data.get('space_type')
        space_number = data.get('space_number')

        try:
            # 调用存储过程处理入场
            cursor.execute("{CALL proc_checkin(?, ?, ?, ?, ?, ?, ?, ?, ?)}", 
                         (plate, gate, has_reservation, reservation_code, 
                          user_name, user_phone, area, space_type, space_number))

            conn.commit()
            return jsonify({'success': True, 'message': '车辆入场成功'})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'message': str(e)})
        finally:
            conn.close()

@app.route('/api/records/exit', methods=['GET', 'POST'])
def get_exit_records():
    """处理出场记录（获取或创建）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        """获取出场记录"""
        try:
            cursor.execute("""
                SELECT o.OutID, o.InID, o.OutTime, o.OutGate, 
                       o.ParkingHours, o.ParkingFee, o.PayStatus,
                       i.CphID
                FROM OutSpace o
                INNER JOIN InSpace i ON o.InID = i.InID
                ORDER BY o.OutTime DESC
            """)

            records = []
            for row in cursor.fetchall():
                records.append({
                    'id': row[0],
                    'in_id': row[1],
                    'time': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None,
                    'gate': row[3],
                    'parking_hours': float(row[4]) if row[4] else 0,
                    'parking_fee': float(row[5]) if row[5] else 0,
                    'pay_status': row[6],
                    'plate': row[7]
                })

            return jsonify({'success': True, 'records': records})
        finally:
            conn.close()

    elif request.method == 'POST':
        """创建出场记录"""
        data = request.json
        plate = data.get('plate')
        gate = data.get('gate')
        payment_status = data.get('payment_status', '未支付')

        try:
            # 查找车辆的入场记录
            cursor.execute("""
                SELECT InID FROM InSpace 
                WHERE CphID = ? AND InID NOT IN (SELECT InID FROM OutSpace)
            """, (plate,))

            result = cursor.fetchone()
            if not result:
                return jsonify({'success': False, 'message': '未找到该车辆的入场记录'})

            in_id = result[0]

            # 调用存储过程处理出场
            cursor.execute("{CALL proc_out(?, ?)}", (in_id, gate))

            conn.commit()
            return jsonify({'success': True, 'message': '车辆出场成功'})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'message': str(e)})
        finally:
            conn.close()

@app.route('/api/reservations/check-violations', methods=['POST'])
def check_reservation_violations():
    """检查预约违约并更新状态"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("EXEC proc_CheckReservationViolation")
        result = cursor.fetchone()

        conn.commit()
        return jsonify({
            'success': True, 
            'message': f'已检查并更新违约预约，共处理 {result[0] if result else 0} 条记录'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/parking/types', methods=['GET'])
def get_parking_types():
    """获取车位类型列表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT TypeID, TypeName, CwSL FROM CwType ORDER BY TypeID")

        types = []
        for row in cursor.fetchall():
            types.append({
                'id': row[0],
                'name': row[1],
                'count': row[2]
            })

        return jsonify({'success': True, 'types': types})
    finally:
        conn.close()

@app.route('/api/reservations/check-violation', methods=['GET'])
def check_reservation_violation():
    """检查预约违约并更新状态（GET方法）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("EXEC proc_CheckReservationViolation")
        result = cursor.fetchone()

        conn.commit()
        violation_count = result[0] if result else 0
        return jsonify({
            'success': True,
            'violation_count': violation_count,
            'message': f'已检查并更新违约预约，共处理 {violation_count} 条记录'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'violation_count': 0,
            'message': str(e)
        })
    finally:
        conn.close()

@app.route('/api/users/batch-import', methods=['POST'])
def batch_import_users():
    """批量导入用户"""
    data = request.json
    users = data.get('users', [])

    if not users:
        return jsonify({'success': False, 'message': '没有要导入的用户数据'})

    conn = get_db_connection()
    cursor = conn.cursor()

    success_count = 0
    error_messages = []

    try:
        for user in users:
            try:
                user_id = user.get('user_id')
                user_name = user.get('user_name')
                user_type = user.get('user_type')
                user_phone = user.get('user_phone', '')
                credit_score = user.get('credit_score', 100)

                # 验证必填字段
                if not user_id or not user_name or not user_type:
                    error_messages.append(f'用户ID {user_id}: 缺少必填字段')
                    continue

                # 验证用户类型
                if user_type not in ['教职工', '学生', '访客']:
                    error_messages.append(f'用户ID {user_id}: 无效的用户类型')
                    continue

                # 检查用户是否已存在
                cursor.execute("SELECT COUNT(*) FROM FjutUser WHERE UserID = ?", (user_id,))
                if cursor.fetchone()[0] > 0:
                    error_messages.append(f'用户ID {user_id}: 用户已存在')
                    continue

                # 插入用户
                cursor.execute("""
                    INSERT INTO FjutUser (UserID, UserName, UserType, UserPhone, CreditScore)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, user_name, user_type, user_phone, credit_score))

                success_count += 1
            except Exception as e:
                error_messages.append(f'用户ID {user.get("user_id")}: {str(e)}')

        conn.commit()

        message = f'成功导入{success_count}个用户'
        if error_messages:
            message += f'，失败{len(error_messages)}个'

        return jsonify({
            'success': True,
            'success_count': success_count,
            'error_count': len(error_messages),
            'errors': error_messages[:10],  # 只返回前10个错误
            'message': message
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/vehicles/batch-import', methods=['POST'])
def batch_import_vehicles():
    """批量导入车辆"""
    data = request.json
    vehicles = data.get('vehicles', [])

    if not vehicles:
        return jsonify({'success': False, 'message': '没有要导入的车辆数据'})

    conn = get_db_connection()
    cursor = conn.cursor()

    success_count = 0
    error_messages = []

    try:
        for vehicle in vehicles:
            try:
                plate = vehicle.get('plate')
                vehicle_type = vehicle.get('vehicle_type')
                user_id = vehicle.get('user_id')

                # 验证必填字段
                if not plate or not vehicle_type:
                    error_messages.append(f'车牌号 {plate}: 缺少必填字段')
                    continue

                # 验证车辆类型
                if vehicle_type not in ['教职工', '学生', '访客', '公务车辆', '特殊车辆']:
                    error_messages.append(f'车牌号 {plate}: 无效的车辆类型')
                    continue

                # 检查车辆是否已存在
                cursor.execute("SELECT COUNT(*) FROM Clgl WHERE CphID = ?", (plate,))
                if cursor.fetchone()[0] > 0:
                    error_messages.append(f'车牌号 {plate}: 车辆已存在')
                    continue

                # 如果有用户ID，验证用户是否存在
                if user_id:
                    cursor.execute("SELECT COUNT(*) FROM FjutUser WHERE UserID = ?", (user_id,))
                    if cursor.fetchone()[0] == 0:
                        error_messages.append(f'车牌号 {plate}: 用户ID {user_id} 不存在')
                        continue

                # 插入车辆
                cursor.execute("""
                    INSERT INTO Clgl (CphID, ClType, UserID)
                    VALUES (?, ?, ?)
                """, (plate, vehicle_type, user_id))

                success_count += 1
            except Exception as e:
                error_messages.append(f'车牌号 {vehicle.get("plate")}: {str(e)}')

        conn.commit()

        message = f'成功导入{success_count}个车辆'
        if error_messages:
            message += f'，失败{len(error_messages)}个'

        return jsonify({
            'success': True,
            'success_count': success_count,
            'error_count': len(error_messages),
            'errors': error_messages[:10],  # 只返回前10个错误
            'message': message
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# ==================== 支付相关接口 ====================

@app.route('/api/payment/pay', methods=['POST'])
def pay_parking_fee():
    """支付停车费接口"""
    data = request.json
    out_id = data.get('out_id')
    
    if not out_id:
        return jsonify({'success': False, 'message': '缺少出场记录ID'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查出场记录是否存在且未支付
        cursor.execute("""
            SELECT OutID, PayStatus, ParkingFee, i.CphID
            FROM OutSpace o
            INNER JOIN InSpace i ON o.InID = i.InID
            WHERE OutID = ?
        """, (out_id,))
        
        record = cursor.fetchone()
        if not record:
            return jsonify({'success': False, 'message': '未找到该出场记录'})
        
        if record[1] == '已支付':
            return jsonify({'success': False, 'message': '该记录已支付，请勿重复支付'})
        
        if record[1] == '免费':
            return jsonify({'success': False, 'message': '该记录为免费记录，无需支付'})
        
        # 调用存储过程更新支付状态
        cursor.execute("EXEC proc_payfee @OutID = ?", (out_id,))
        
        conn.commit()
        return jsonify({
            'success': True, 
            'message': '支付成功',
            'plate': record[3],
            'fee': float(record[2]) if record[2] else 0
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/payment/status/<int:out_id>', methods=['GET'])
def get_payment_status(out_id):
    """获取支付状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT o.OutID, o.PayStatus, o.ParkingFee, o.ParkingHours, 
                   o.OutTime, i.CphID, i.InTime
            FROM OutSpace o
            INNER JOIN InSpace i ON o.InID = i.InID
            WHERE o.OutID = ?
        """, (out_id,))
        
        record = cursor.fetchone()
        if not record:
            return jsonify({'success': False, 'message': '未找到该出场记录'})
        
        return jsonify({
            'success': True,
            'out_id': record[0],
            'pay_status': record[1],
            'parking_fee': float(record[2]) if record[2] else 0,
            'parking_hours': float(record[3]) if record[3] else 0,
            'out_time': record[4].strftime('%Y-%m-%d %H:%M:%S') if record[4] else None,
            'plate': record[5],
            'in_time': record[6].strftime('%Y-%m-%d %H:%M:%S') if record[6] else None
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/payment/unpaid', methods=['GET'])
def get_unpaid_records():
    """获取所有未支付的出场记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT o.OutID, o.PayStatus, o.ParkingFee, o.ParkingHours, 
                   o.OutTime, i.CphID, i.InTime
            FROM OutSpace o
            INNER JOIN InSpace i ON o.InID = i.InID
            WHERE o.PayStatus = '未支付'
            ORDER BY o.OutTime DESC
        """)
        
        records = []
        for row in cursor.fetchall():
            records.append({
                'out_id': row[0],
                'pay_status': row[1],
                'parking_fee': float(row[2]) if row[2] else 0,
                'parking_hours': float(row[3]) if row[3] else 0,
                'out_time': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else None,
                'plate': row[5],
                'in_time': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None
            })
        
        return jsonify({'success': True, 'records': records})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
