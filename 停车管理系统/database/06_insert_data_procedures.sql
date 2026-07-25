USE fjutspace
GO

-- ============================================
-- 用户表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertUser
    @UserID INT,
    @UserName NVARCHAR(50),
    @UserType NVARCHAR(20),
    @UserPhone NVARCHAR(20),
    @CreditScore INT = 100
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户ID是否已存在
    IF EXISTS (SELECT 1 FROM FjutUser WHERE UserID = @UserID)
    BEGIN
        RAISERROR('用户ID已存在', 16, 1)
        RETURN
    END

    -- 插入用户信息
    INSERT INTO FjutUser(UserID, UserName, UserType, UserPhone, CreditScore)
    VALUES(@UserID, @UserName, @UserType, @UserPhone, @CreditScore)

    PRINT '用户信息插入成功'
END
GO

-- ============================================
-- 车辆信息表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertVehicle
    @CphID NVARCHAR(20),
    @ClType NVARCHAR(20),
    @UserID INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查车牌号是否已存在
    IF EXISTS (SELECT 1 FROM Clgl WHERE CphID = @CphID)
    BEGIN
        RAISERROR('车牌号已存在', 16, 1)
        RETURN
    END

    -- 检查用户是否存在（仅对非公务车辆和非特殊车辆进行检查）
    IF @ClType NOT IN ('公务车辆', '特殊车辆') AND NOT EXISTS (SELECT 1 FROM FjutUser WHERE UserID = @UserID)
    BEGIN
        RAISERROR('用户不存在', 16, 1)
        RETURN
    END

    -- 插入车辆信息
    INSERT INTO Clgl(CphID, ClType, UserID)
    VALUES(@CphID, @ClType, @UserID)

    PRINT '车辆信息插入成功'
END
GO

-- ============================================
-- 车位类型表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertCwType
    @TypeID INT,
    @TypeName NVARCHAR(20),
    @CwSL INT = 0
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查类型ID是否已存在
    IF EXISTS (SELECT 1 FROM CwType WHERE TypeID = @TypeID)
    BEGIN
        RAISERROR('车位类型ID已存在', 16, 1)
        RETURN
    END

    -- 插入车位类型信息
    INSERT INTO CwType(TypeID, TypeName, CwSL)
    VALUES(@TypeID, @TypeName, @CwSL)

    PRINT '车位类型信息插入成功'
END
GO

-- ============================================
-- 车位表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertParkingSpace
    @CwID INT,
    @Cwbh VARCHAR(20),
    @Area NVARCHAR(20),
    @TypeID INT,
    @Status NVARCHAR(20) = '空闲'
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查车位编号是否已存在
    IF EXISTS (SELECT 1 FROM Cwgl WHERE Cwbh = @Cwbh)
    BEGIN
        RAISERROR('车位编号已存在', 16, 1)
        RETURN
    END

    -- 检查车位类型是否存在
    IF NOT EXISTS (SELECT 1 FROM CwType WHERE TypeID = @TypeID)
    BEGIN
        RAISERROR('车位类型不存在', 16, 1)
        RETURN
    END

    -- 插入车位信息
    INSERT INTO Cwgl(CwID, Cwbh, Area, TypeID, Status)
    VALUES(@CwID, @Cwbh, @Area, @TypeID, @Status)

    -- 如果车位状态为空闲，更新车位类型数量表
    IF @Status = '空闲'
    BEGIN
        UPDATE CwType
        SET CwSL = CwSL + 1
        WHERE TypeID = @TypeID
    END

    PRINT '车位信息插入成功'
END
GO

-- ============================================
-- 车位预约表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertReservation
    @ReservationID INT,
    @UserID INT,
    @TypeID INT,
    @CwID INT,
    @CphID NVARCHAR(20),
    @StartTime DATETIME,
    @EndTime DATETIME,
    @Purpose NVARCHAR(200) = NULL,
    @Status NVARCHAR(20) = '待审批'
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查预约ID是否已存在
    IF EXISTS (SELECT 1 FROM ParkingReservations WHERE ReservationID = @ReservationID)
    BEGIN
        RAISERROR('预约ID已存在', 16, 1)
        RETURN
    END

    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM FjutUser WHERE UserID = @UserID)
    BEGIN
        RAISERROR('用户不存在', 16, 1)
        RETURN
    END

    -- 检查车位类型是否存在
    IF NOT EXISTS (SELECT 1 FROM CwType WHERE TypeID = @TypeID)
    BEGIN
        RAISERROR('车位类型不存在', 16, 1)
        RETURN
    END

    -- 检查车位是否存在
    IF NOT EXISTS (SELECT 1 FROM Cwgl WHERE CwID = @CwID)
    BEGIN
        RAISERROR('车位不存在', 16, 1)
        RETURN
    END

    -- 检查车牌号是否存在
    IF NOT EXISTS (SELECT 1 FROM Clgl WHERE CphID = @CphID)
    BEGIN
        RAISERROR('车牌号不存在', 16, 1)
        RETURN
    END

    -- 检查预约时间是否冲突
    IF EXISTS (
        SELECT 1 FROM ParkingReservations
        WHERE CwID = @CwID
        AND Status IN ('待审批', '已批准')
        AND (
            (@StartTime >= StartTime AND @StartTime < EndTime)
            OR (@EndTime > StartTime AND @EndTime <= EndTime)
            OR (@StartTime <= StartTime AND @EndTime >= EndTime)
        )
    )
    BEGIN
        RAISERROR('该车位在指定时间段已有预约', 16, 1)
        RETURN
    END

    -- 插入预约信息
    INSERT INTO ParkingReservations(
        ReservationID, UserID, TypeID, CwID, CphID,
        StartTime, EndTime, Purpose, Status
    )
    VALUES(
        @ReservationID, @UserID, @TypeID, @CwID, @CphID,
        @StartTime, @EndTime, @Purpose, @Status
    )

    PRINT '预约信息插入成功'
END
GO

-- ============================================
-- 车辆入场记录表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertEntry
    @InID INT,
    @CphID NVARCHAR(20),
    @InTime DATETIME = NULL,
    @InGate NVARCHAR(50) = NULL,
    @CwID INT = NULL,
    @ReservationID INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查入场ID是否已存在
    IF EXISTS (SELECT 1 FROM InSpace WHERE InID = @InID)
    BEGIN
        RAISERROR('入场ID已存在', 16, 1)
        RETURN
    END

    -- 检查车牌号是否存在
    IF NOT EXISTS (SELECT 1 FROM Clgl WHERE CphID = @CphID)
    BEGIN
        RAISERROR('车牌号不存在', 16, 1)
        RETURN
    END

    -- 检查车位是否存在（如果提供了车位ID）
    IF @CwID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM Cwgl WHERE CwID = @CwID)
    BEGIN
        RAISERROR('车位不存在', 16, 1)
        RETURN
    END

    -- 检查预约是否存在（如果提供了预约ID）
    IF @ReservationID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM ParkingReservations WHERE ReservationID = @ReservationID)
    BEGIN
        RAISERROR('预约不存在', 16, 1)
        RETURN
    END

    -- 设置默认入场时间
    IF @InTime IS NULL
        SET @InTime = GETDATE()

    -- 插入入场记录
    INSERT INTO InSpace(InID, CphID, InTime, InGate, CwID, ReservationID)
    VALUES(@InID, @CphID, @InTime, @InGate, @CwID, @ReservationID)

    PRINT '入场记录插入成功'
END
GO

-- ============================================
-- 车辆出场记录表插入存储过程
-- ============================================
CREATE PROCEDURE proc_InsertExit
    @OutID INT,
    @InID INT,
    @OutTime DATETIME = NULL,
    @OutGate NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查出场ID是否已存在
    IF EXISTS (SELECT 1 FROM OutSpace WHERE OutID = @OutID)
    BEGIN
        RAISERROR('出场ID已存在', 16, 1)
        RETURN
    END

    -- 检查入场记录是否存在
    IF NOT EXISTS (SELECT 1 FROM InSpace WHERE InID = @InID)
    BEGIN
        RAISERROR('入场记录不存在', 16, 1)
        RETURN
    END

    -- 检查是否已有出场记录
    IF EXISTS (SELECT 1 FROM OutSpace WHERE InID = @InID)
    BEGIN
        RAISERROR('该入场记录已有出场记录', 16, 1)
        RETURN
    END

    -- 设置默认出场时间
    IF @OutTime IS NULL
        SET @OutTime = GETDATE()

    -- 计算停车时长和费用
    DECLARE @Hours DECIMAL(10,2)
    DECLARE @Fee DECIMAL(10,2)
    DECLARE @PayStatus NVARCHAR(20)

    SELECT @Hours = ParkingHours, @Fee = ParkingFee
    FROM dbo.func_hour_fee(@InID, @OutTime)

    -- 确定支付状态
    IF @Fee = 0
        SET @PayStatus = '免费'
    ELSE
        SET @PayStatus = '未支付'

    -- 插入出场记录
    INSERT INTO OutSpace(OutID, InID, OutTime, OutGate, ParkingHours, ParkingFee, PayStatus)
    VALUES(@OutID, @InID, @OutTime, @OutGate, @Hours, @Fee, @PayStatus)

    PRINT '出场记录插入成功，停车时长: ' + CAST(@Hours AS NVARCHAR(20)) + '小时，费用: ' + CAST(@Fee AS NVARCHAR(20)) + '元'
END
GO

PRINT '所有插入数据的存储过程创建成功！'
GO