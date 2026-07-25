
USE fjutspace
GO

-- 删除旧的存储过程
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[proc_CheckReservationViolation]') AND type in (N'P', N'PC'))
DROP PROCEDURE [dbo].[proc_CheckReservationViolation]
GO

-- 检查预约违约的存储过程
CREATE PROCEDURE proc_CheckReservationViolation
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ViolationCount INT = 0;

    -- 创建临时表存储违约预约信息
    CREATE TABLE #ViolationReservations (
        ReservationID INT,
        CwID INT,
        UserID INT
    );

    -- 查找超过预约开始时间30分钟且状态为"已批准"的预约
    INSERT INTO #ViolationReservations (ReservationID, CwID, UserID)
    SELECT pr.ReservationID, pr.CwID, pr.UserID
    FROM ParkingReservations pr
    WHERE pr.Status = '已批准'
      AND pr.StartTime < DATEADD(MINUTE, -30, GETDATE())
      AND NOT EXISTS (
          -- 排除已经入场的预约
          SELECT 1 FROM InSpace i
          WHERE i.ReservationID = pr.ReservationID
          AND i.InID NOT IN (SELECT InID FROM OutSpace)
      );

    -- 获取违约预约数量
    SELECT @ViolationCount = COUNT(*) FROM #ViolationReservations;

    -- 更新预约状态为"违约"并扣除用户10信用分
    UPDATE pr
    SET pr.Status = '违约'
    FROM ParkingReservations pr
    INNER JOIN #ViolationReservations vr ON pr.ReservationID = vr.ReservationID;

    UPDATE fu
    SET fu.CreditScore = fu.CreditScore - 10
    FROM FjutUser fu
    INNER JOIN #ViolationReservations vr ON fu.UserID = vr.UserID;

    -- 释放预约车位为空闲
    UPDATE cw
    SET cw.Status = '空闲'
    FROM Cwgl cw
    INNER JOIN #ViolationReservations vr ON cw.CwID = vr.CwID;

    -- 删除临时表
    DROP TABLE #ViolationReservations;

    -- 返回被标记为违约的预约数量
    SELECT @ViolationCount AS ViolationCount;
END
GO

-- 创建定时作业来定期检查预约违约（需要SQL Server Agent支持）
-- 如果没有SQL Server Agent，可以在应用启动时或定时调用此存储过程
