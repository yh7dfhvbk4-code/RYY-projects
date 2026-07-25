USE fjutspace
GO

-- 时长费用计算函数
CREATE FUNCTION func_hour_fee(
    @InID INT,
    @OutTime DATETIME
)
RETURNS @result TABLE(
    ParkingHours DECIMAL(10,2),
    ParkingFee DECIMAL(10,2)
)
AS
BEGIN
    DECLARE @Hours DECIMAL(10,2)
    DECLARE @Fee DECIMAL(10,2)
    DECLARE @ClType NVARCHAR(20)
    DECLARE @InTime DATETIME

    -- 获取车辆类型和入场时间
    SELECT @InTime = InTime, @ClType = ClType 
    FROM InSpace i
    INNER JOIN Clgl c ON i.CphID = c.CphID
    WHERE i.InID = @InID

    -- 计算停车时长
    SET @Hours = DATEDIFF(SECOND, @InTime, @OutTime) / 3600.0

    -- 根据车辆类型计费
    IF @ClType = '特殊车辆'
        SET @Fee = 0  -- 特殊车辆免费
    ELSE IF @ClType = '公务车辆'
        SET @Fee = 0  -- 公务车辆免费
    ELSE IF @ClType = '教职工'
        SET @Fee = 0  -- 教职工车辆免费
    ELSE IF @Hours < 0.5
        SET @Fee = 0  -- 短时间免费
    ELSE
        SET @Fee = CEILING(@Hours) * 2.0  -- 学生和访客车辆2元/小时

    INSERT INTO @result VALUES(@Hours, @Fee)
    RETURN
END
GO

-- 车辆出场存储过程
CREATE PROCEDURE proc_out
    @InID INT,
    @OutGate NVARCHAR(50) = '未指定'
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @CphID NVARCHAR(20)
    DECLARE @InTime DATETIME
    DECLARE @OutTime DATETIME
    DECLARE @Hours DECIMAL(10,2)
    DECLARE @Fee DECIMAL(10,2)
    DECLARE @CwID INT
    DECLARE @PayStatus NVARCHAR(20)
    DECLARE @OutID INT

    -- 获取入场信息
    SELECT @CphID = CphID, @InTime = InTime, @CwID = CwID
    FROM InSpace WHERE InID = @InID

    IF @CphID IS NULL
    BEGIN
        RAISERROR('未找到该入场记录', 16, 1)
        RETURN
    END

    -- 设置出场时间
    SET @OutTime = GETDATE()

    -- 计算费用
    SELECT @Hours = ParkingHours, @Fee = ParkingFee
    FROM dbo.func_hour_fee(@InID, @OutTime)

    -- 确定支付状态
    IF @Fee = 0
        SET @PayStatus = '免费'
    ELSE
        SET @PayStatus = '未支付'

    -- 生成新的OutID
    SELECT @OutID = ISNULL(MAX(OutID), 0) + 1 FROM OutSpace;

    -- 插入出场记录
    INSERT INTO OutSpace(
        OutID, InID, OutTime, OutGate, ParkingHours, ParkingFee, PayStatus
    )
    VALUES(
        @OutID, @InID, @OutTime, @OutGate, @Hours, @Fee, @PayStatus
    )

    -- 更新车位状态为空闲
    IF @CwID IS NOT NULL
    BEGIN
        UPDATE Cwgl SET Status = '空闲' WHERE CwID = @CwID
    END

    PRINT '出场登记成功，停车时长: ' + CAST(@Hours AS NVARCHAR(20)) + '小时，费用: ' + CAST(@Fee AS NVARCHAR(20)) + '元'
END
GO

-- 停车费支付存储过程
CREATE PROCEDURE proc_payfee
    @OutID INT
AS
BEGIN
    SET NOCOUNT ON;

    -- 更新支付状态
    UPDATE OutSpace
    SET PayStatus = '已支付'
    WHERE OutID = @OutID

    IF @@ROWCOUNT > 0
        PRINT '支付成功'
    ELSE
        PRINT '未找到该出场记录'
END
GO

-- 车位状态更新触发器
-- 入场时更新车位状态
CREATE TRIGGER tri_UpdateSpaceStatusOnEntry
ON InSpace
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE Cwgl
    SET Status = '占用'
    WHERE CwID IN (SELECT CwID FROM inserted WHERE CwID IS NOT NULL)
END
GO

-- 出场时更新车位状态
CREATE TRIGGER tri_UpdateSpaceStatusOnExit
ON OutSpace
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE Cwgl
    SET Status = '空闲'
    WHERE CwID IN (
        SELECT i.CwID 
        FROM InSpace i
        INNER JOIN inserted o ON i.InID = o.InID
        WHERE i.CwID IS NOT NULL
    )
END
GO
