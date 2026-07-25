
USE fjutspace
GO

-- 删除旧的存储过程
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[proc_checkin]') AND type in (N'P', N'PC'))
DROP PROCEDURE [dbo].[proc_checkin]
GO

-- 车辆入场存储过程（更新版：支持提前半小时入场）
CREATE PROCEDURE proc_checkin
    @CphID NVARCHAR(20),
    @InGate NVARCHAR(50),
    @HasReservation BIT,
    @ReservationCode INT = NULL,
    @UserName NVARCHAR(50) = NULL,
    @UserPhone NVARCHAR(20) = NULL,
    @Area NVARCHAR(20) = NULL,
    @SpaceTypeName NVARCHAR(20) = NULL,
    @SpaceNumber VARCHAR(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ReservationID INT;
    DECLARE @InID INT;
    DECLARE @CwID INT;
    DECLARE @TypeID INT;
    DECLARE @ClType NVARCHAR(20);
    DECLARE @UserID INT;

    -- 检查车辆是否已经在场内
    IF EXISTS (
        SELECT 1 FROM InSpace
        WHERE CphID = @CphID
        AND InID NOT IN (SELECT InID FROM OutSpace)
    )
    BEGIN
        RAISERROR('车辆已在场内，不能重复入场', 16, 1);
        RETURN;
    END

    -- 如果有预约
    IF @HasReservation = 1
    BEGIN
        -- 验证预约码（允许提前半小时入场）
        SELECT @ReservationID = pr.ReservationID,
               @CwID = pr.CwID,
               @UserID = pr.UserID,
               @ClType = c.ClType
        FROM ParkingReservations pr
        INNER JOIN Clgl c ON pr.CphID = c.CphID
        WHERE pr.ReservationID = @ReservationCode
          AND pr.CphID = @CphID
          AND pr.Status = '已批准'
          AND GETDATE() BETWEEN DATEADD(MINUTE, -30, pr.StartTime) AND pr.EndTime;

        IF @ReservationID IS NULL
        BEGIN
            RAISERROR('预约码无效或已过期', 16, 1);
            RETURN;
        END

        -- 更新预约状态为已使用
        UPDATE ParkingReservations
        SET Status = '已使用'
        WHERE ReservationID = @ReservationID;

        -- 更新车位状态为占用
        UPDATE Cwgl
        SET Status = '占用'
        WHERE CwID = @CwID;
    END
    ELSE
    BEGIN
        -- 检查车辆是否存在
        IF EXISTS (SELECT 1 FROM Clgl WHERE CphID = @CphID)
        BEGIN
            -- 获取车辆类型和用户ID
            SELECT @ClType = ClType, @UserID = UserID
            FROM Clgl WHERE CphID = @CphID;
        END
        ELSE
        BEGIN
            -- 车辆不存在，创建访客用户和车辆
            IF @UserName IS NULL OR @UserPhone IS NULL
            BEGIN
                RAISERROR('车辆不存在，请提供用户姓名和电话号码', 16, 1);
                RETURN;
            END

            -- 生成新的用户ID
            SELECT @UserID = ISNULL(MAX(UserID), 0) + 1 FROM FjutUser;

            -- 检查用户是否已存在
            IF NOT EXISTS (SELECT 1 FROM FjutUser WHERE UserPhone = @UserPhone)
            BEGIN
                -- 创建访客用户
                INSERT INTO FjutUser(UserID, UserName, UserType, UserPhone, CreditScore)
                VALUES (@UserID, @UserName, '访客', @UserPhone, 100);
            END
            ELSE
            BEGIN
                -- 获取已存在用户的ID
                SELECT @UserID = UserID FROM FjutUser WHERE UserPhone = @UserPhone;
            END

            -- 设置车辆类型为访客
            SET @ClType = '访客';

            -- 创建车辆信息
            INSERT INTO Clgl(CphID, ClType, UserID)
            VALUES (@CphID, @ClType, @UserID);
        END

        -- 获取车位类型ID
        SELECT @TypeID = TypeID FROM CwType WHERE TypeName = @SpaceTypeName;

        IF @TypeID IS NULL
        BEGIN
            RAISERROR('无效的车位类型', 16, 1);
            RETURN;
        END

        -- 查找指定区域、类型和车位号的车位
        SELECT @CwID = CwID
        FROM Cwgl
        WHERE Area = @Area
          AND TypeID = @TypeID
          AND Cwbh = @SpaceNumber
          AND Status = '空闲';

        IF @CwID IS NULL
        BEGIN
            RAISERROR('该区域没有可用的车位', 16, 1);
            RETURN;
        END

        -- 更新车位状态为占用
        UPDATE Cwgl
        SET Status = '占用'
        WHERE CwID = @CwID;
    END

    -- 生成新的InID
    SELECT @InID = ISNULL(MAX(InID), 0) + 1 FROM InSpace;

    -- 如果是特殊车辆，直接放行
    IF @ClType = '特殊车辆'
    BEGIN
        INSERT INTO InSpace(InID, CphID, InGate)
        VALUES (@InID, @CphID, @InGate);
        PRINT '特殊车辆已放行';
        RETURN;
    END

    -- 记录车辆入场
    IF @HasReservation = 1
    BEGIN
        INSERT INTO InSpace(InID, CphID, InGate, CwID, ReservationID)
        VALUES (@InID, @CphID, @InGate, @CwID, @ReservationID);
        PRINT '已记录入场，请前往预约车位';
    END
    ELSE
    BEGIN
        INSERT INTO InSpace(InID, CphID, InGate, CwID)
        VALUES (@InID, @CphID, @InGate, @CwID);
        PRINT '已记录入场，请前往指定车位';
    END
END
GO
