USE fjutspace
GO

-- 创建车位预约存储过程
CREATE PROCEDURE proc_CreateParkingReservation
    @UserID INT,
    @CphID NVARCHAR(20),
    @CwID INT,
    @StartTime DATETIME,
    @EndTime DATETIME,
    @Purpose NVARCHAR(200),
    @ReservationID INT OUTPUT
AS
BEGIN
SET NOCOUNT ON;

BEGIN TRY
BEGIN TRANSACTION;

-- 1. 检查时间合法性
IF @StartTime >= @EndTime
BEGIN
    RAISERROR('开始时间不能大于等于结束时间',16,1);
    RETURN;
END

IF @StartTime < GETDATE()
BEGIN
    RAISERROR('不能预约过去的时间',16,1);
    RETURN;
END

-- 2. 检查用户信用分
DECLARE @CreditScore INT;
SELECT @CreditScore = CreditScore FROM FjutUser WHERE UserID = @UserID;
IF @CreditScore < 60
BEGIN
    RAISERROR('信用分过低，无法预约车位',16,1);
    RETURN;
END

-- 3. 获取车辆信息
DECLARE @OwnerID INT;
DECLARE @ClType NVARCHAR(20);
SELECT @OwnerID = UserID, @ClType = ClType FROM Clgl WHERE CphID = @CphID;

-- 4. 检查车辆归属
IF @ClType NOT IN ('公务车辆','特殊车辆')
BEGIN
    IF @OwnerID <> @UserID
    BEGIN
        RAISERROR('该车辆不属于当前用户',16,1);
        RETURN;
    END
END

-- 5. 检查用户重复预约
IF @ClType NOT IN ('公务车辆','特殊车辆')
BEGIN
    IF EXISTS (
        SELECT 1 FROM ParkingReservations
        WHERE UserID = @UserID AND Status IN ('待审批','已批准')
        AND ((@StartTime BETWEEN StartTime AND EndTime) OR (@EndTime BETWEEN StartTime AND EndTime)
        OR (StartTime BETWEEN @StartTime AND @EndTime) OR (EndTime BETWEEN @StartTime AND @EndTime))
    )
    BEGIN
        RAISERROR('该时间段已有预约',16,1);
        RETURN;
    END
END

-- 6. 获取车位类型
DECLARE @CwTypeID INT;
DECLARE @CwTypeName NVARCHAR(20);
SELECT @CwTypeID = TypeID FROM Cwgl WHERE CwID = @CwID;
SELECT @CwTypeName = TypeName FROM CwType WHERE TypeID = @CwTypeID;

-- 7. 检查车位是否可用
IF NOT EXISTS (SELECT 1 FROM Cwgl WHERE CwID = @CwID AND Status = '空闲')
BEGIN
    RAISERROR('所选车位不存在或当前不可用',16,1);
    RETURN;
END

-- 8. 检查车位时段冲突
IF EXISTS (
    SELECT 1 FROM ParkingReservations
    WHERE CwID = @CwID AND Status IN ('待审批','已批准')
    AND ((@StartTime BETWEEN StartTime AND EndTime) OR (@EndTime BETWEEN StartTime AND EndTime)
    OR (StartTime BETWEEN @StartTime AND @EndTime) OR (EndTime BETWEEN @StartTime AND @EndTime))
)
BEGIN
    RAISERROR('该车位在所选时间段已被预约',16,1);
    RETURN;
END

-- 9. 车辆与车位类型匹配校验
IF @ClType = '公务车辆' AND @CwTypeName NOT IN ( '公务车位', '充电桩')
        BEGIN
            RAISERROR('公务车辆只能预约公务车位或充电桩', 16, 1);
            RETURN;
        END

        IF @ClType = '教职工' AND @CwTypeName NOT IN ('固定车位', '临时车位', '充电桩')
        BEGIN
            RAISERROR('教职工车辆只能预约固定车位、临时车位或充电桩', 16, 1);
            RETURN;
        END

        IF @ClType IN ('学生', '访客') AND @CwTypeName NOT IN ( '临时车位', '充电桩')
        BEGIN
            RAISERROR('学生和访客车辆只能预约临时车位或充电桩', 16, 1);
            RETURN;
        END
        
        IF @ClType = '特殊车辆' AND @CwTypeName NOT IN ( '临时车位', '充电桩')
        BEGIN
            RAISERROR('特殊车辆只能预约临时车位或充电桩', 16, 1);
            RETURN;
        END

-- 10. 创建预约
-- 获取下一个可用的ReservationID
SELECT @ReservationID = ISNULL(MAX(ReservationID), 0) + 1 FROM ParkingReservations;

INSERT INTO ParkingReservations (ReservationID, UserID, TypeID, CwID, CphID, StartTime, EndTime, Purpose, Status)
VALUES (@ReservationID, @UserID, @CwTypeID, @CwID, @CphID, @StartTime, @EndTime, @Purpose, '待审批');

-- 11. 更新车位状态
UPDATE Cwgl SET Status = '预留' WHERE CwID = @CwID AND Status = '空闲';

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
IF @@TRANCOUNT > 0
ROLLBACK TRANSACTION;

DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
DECLARE @ErrorState INT = ERROR_STATE();
RAISERROR(@ErrorMessage,@ErrorSeverity,@ErrorState);
END CATCH
END
GO

-- 审批预约
CREATE PROCEDURE proc_ApproveReservation
    @ReservationID INT,
    @Approve BIT
AS
BEGIN
SET NOCOUNT ON;
BEGIN TRY
BEGIN TRANSACTION;

IF NOT EXISTS (SELECT 1 FROM ParkingReservations WHERE ReservationID = @ReservationID AND Status = '待审批')
BEGIN
    RAISERROR('预约不存在或已处理',16,1);
    RETURN;
END

DECLARE @CwID INT;
SELECT @CwID = CwID FROM ParkingReservations WHERE ReservationID = @ReservationID;

IF @Approve = 1
BEGIN
    UPDATE ParkingReservations SET Status = '已批准' WHERE ReservationID = @ReservationID;
END
ELSE
BEGIN
    UPDATE ParkingReservations SET Status = '已取消' WHERE ReservationID = @ReservationID;
    UPDATE Cwgl SET Status = '空闲' WHERE CwID = @CwID AND Status = '预留';
END

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
IF @@TRANCOUNT > 0
ROLLBACK TRANSACTION;
DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
DECLARE @ErrorState INT = ERROR_STATE();
RAISERROR(@ErrorMessage,@ErrorSeverity,@ErrorState);
END CATCH
END
GO

-- 获取可用车位
CREATE PROCEDURE proc_GetAvailableSpaces
    @ClType NVARCHAR(20),
    @Area NVARCHAR(20) = NULL,
    @TypeID INT = NULL
AS
BEGIN
SET NOCOUNT ON;
DECLARE @ValidTypes TABLE(TypeID INT,TypeName NVARCHAR(20));
INSERT INTO @ValidTypes SELECT TypeID,TypeName FROM CwType WHERE TypeName = '充电桩';

IF @ClType = '公务车辆'
BEGIN
    INSERT INTO @ValidTypes SELECT TypeID,TypeName FROM CwType WHERE TypeName = '公务车位';
END
ELSE IF @ClType = '特殊车辆'
BEGIN
    INSERT INTO @ValidTypes SELECT TypeID,TypeName FROM CwType WHERE TypeName = '临时车位';
END
ELSE
BEGIN
    IF @ClType = '教职工'
    BEGIN
        INSERT INTO @ValidTypes SELECT TypeID,TypeName FROM CwType WHERE TypeName IN ('固定车位','临时车位');
    END
    ELSE
    BEGIN
        IF @ClType IN ('学生','访客')
        BEGIN
            INSERT INTO @ValidTypes SELECT TypeID,TypeName FROM CwType WHERE TypeName = '临时车位';
        END
    END
END

SELECT cw.CwID,cw.Cwbh,cw.Area,cw.Status,ct.TypeID,ct.TypeName
FROM Cwgl cw
JOIN @ValidTypes vt ON cw.TypeID = vt.TypeID
JOIN CwType ct ON cw.TypeID = ct.TypeID
WHERE cw.Status = '空闲'
AND (@Area IS NULL OR cw.Area = @Area)
AND (@TypeID IS NULL OR cw.TypeID = @TypeID)
ORDER BY cw.Area,ct.TypeName,cw.Cwbh;
END
GO

-- 获取用户车辆
CREATE PROCEDURE proc_GetUserVehicles
    @UserID INT = NULL
AS
BEGIN
SET NOCOUNT ON;
IF @UserID IS NULL
BEGIN
    SELECT c.CphID,c.ClType,c.UserID,
    CASE WHEN c.UserID IS NULL THEN '公共车辆' ELSE fu.UserName END AS OwnerName
    FROM Clgl c LEFT JOIN FjutUser fu ON c.UserID = fu.UserID
    WHERE c.ClType IN ('公务车辆','特殊车辆') ORDER BY c.ClType,c.CphID;
END
ELSE
BEGIN
    SELECT c.CphID,c.ClType,c.UserID,fu.UserName AS OwnerName
    FROM Clgl c LEFT JOIN FjutUser fu ON c.UserID = fu.UserID
    WHERE c.UserID = @UserID ORDER BY c.CphID;
END
END
GO

-- 取消预约
CREATE PROCEDURE proc_CancelReservation
    @ReservationID INT,
    @UserID INT,
    @Reason NVARCHAR(200) = NULL
AS
BEGIN
SET NOCOUNT ON;
BEGIN TRY
BEGIN TRANSACTION;

-- 检查预约是否存在
IF NOT EXISTS (SELECT 1 FROM ParkingReservations WHERE ReservationID = @ReservationID)
BEGIN
    RAISERROR('预约不存在',16,1);
    RETURN;
END

-- 获取预约的用户ID
DECLARE @ActualUserID INT;
SELECT @ActualUserID = UserID FROM ParkingReservations WHERE ReservationID = @ReservationID;

-- 如果提供了UserID，则检查是否匹配
IF @UserID IS NOT NULL AND @ActualUserID IS NOT NULL AND @UserID <> @ActualUserID
BEGIN
    RAISERROR('无权操作此预约',16,1);
    RETURN;
END

-- 如果预约有用户ID，但未提供UserID参数，则不允许取消
IF @ActualUserID IS NOT NULL AND @UserID IS NULL
BEGIN
    RAISERROR('需要提供用户ID才能取消此预约',16,1);
    RETURN;
END

DECLARE @Status NVARCHAR(20);
DECLARE @CwID INT;
SELECT @Status = Status,@CwID = CwID FROM ParkingReservations WHERE ReservationID = @ReservationID;

IF @Status NOT IN ('待审批','已批准')
BEGIN
    RAISERROR('该预约状态不允许取消',16,1);
    RETURN;
END

UPDATE ParkingReservations SET Status = '已取消' WHERE ReservationID = @ReservationID;
UPDATE Cwgl SET Status = '空闲' WHERE CwID = @CwID AND Status = '预留';

COMMIT TRANSACTION;
END TRY
BEGIN CATCH
IF @@TRANCOUNT > 0
ROLLBACK TRANSACTION;
DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
DECLARE @ErrorState INT = ERROR_STATE();
RAISERROR(@ErrorMessage,@ErrorSeverity,@ErrorState);
END CATCH
END
GO

-- 用户预约记录
CREATE PROCEDURE proc_GetUserReservations
    @UserID INT,
    @Status NVARCHAR(20) = NULL
AS
BEGIN
SET NOCOUNT ON;
SELECT pr.ReservationID,pr.UserID,fu.UserName,pr.CphID,cl.ClType,pr.CwID,cw.Cwbh,
cw.Area,ct.TypeName,pr.StartTime,pr.EndTime,pr.Purpose,pr.Status
FROM ParkingReservations pr
JOIN FjutUser fu ON pr.UserID = fu.UserID
JOIN Clgl cl ON pr.CphID = cl.CphID
JOIN Cwgl cw ON pr.CwID = cw.CwID
JOIN CwType ct ON pr.TypeID = ct.TypeID
WHERE pr.UserID = @UserID
AND (@Status IS NULL OR pr.Status = @Status)
ORDER BY pr.StartTime DESC;
END
GO

-- 管理员所有预约
CREATE PROCEDURE proc_GetAllReservations
    @Status NVARCHAR(20) = NULL,
    @StartDate DATETIME = NULL,
    @EndDate DATETIME = NULL
AS
BEGIN
SET NOCOUNT ON;
SELECT pr.ReservationID,pr.UserID,fu.UserName,fu.UserType,pr.CphID,cl.ClType,pr.CwID,
cw.Cwbh,cw.Area,ct.TypeName,pr.StartTime,pr.EndTime,pr.Purpose,pr.Status
FROM ParkingReservations pr
JOIN FjutUser fu ON pr.UserID = fu.UserID
JOIN Clgl cl ON pr.CphID = cl.CphID
JOIN Cwgl cw ON pr.CwID = cw.CwID
JOIN CwType ct ON pr.TypeID = ct.TypeID
WHERE (@Status IS NULL OR pr.Status = @Status)
AND (@StartDate IS NULL OR pr.StartTime >= @StartDate)
AND (@EndDate IS NULL OR pr.EndTime <= @EndDate)
ORDER BY pr.StartTime DESC;
END
GO

PRINT '预约相关存储过程创建完成！'
GO