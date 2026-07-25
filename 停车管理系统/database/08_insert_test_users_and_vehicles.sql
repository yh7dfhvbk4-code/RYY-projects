USE fjutspace
GO

-- ============================================
-- 插入测试用户和车辆数据
-- ============================================

-- 声明变量
DECLARE @UserID INT = 1
DECLARE @Counter INT = 1
DECLARE @UserType NVARCHAR(20)
DECLARE @ClType NVARCHAR(20)
DECLARE @UserName NVARCHAR(50)
DECLARE @UserPhone NVARCHAR(20)
DECLARE @CphID VARCHAR(20)

PRINT '开始插入测试用户和车辆...'
PRINT ''

-- ============================================
-- 插入教职工用户和车辆（3人）
-- ============================================
SET @Counter = 1
WHILE @Counter <= 3
BEGIN
    SET @UserID = @Counter
    SET @UserName = '教职工' + RIGHT('000' + CAST(@Counter AS VARCHAR(3)), 3)
    SET @UserType = '教职工'
    SET @UserPhone = '138' + RIGHT('00000000' + CAST(@Counter AS VARCHAR(8)), 8)
    SET @CphID = '闽A' + RIGHT('00000' + CAST(@Counter AS VARCHAR(5)), 5)

    -- 插入教职工用户
    EXEC proc_InsertUser
        @UserID = @UserID,
        @UserName = @UserName,
        @UserType = @UserType,
        @UserPhone = @UserPhone,
        @CreditScore = 100

    -- 插入教职工车辆
    EXEC proc_InsertVehicle
        @CphID = @CphID,
        @ClType = '教职工',
        @UserID = @UserID

    SET @Counter = @Counter + 1
END

PRINT '已插入3个教职工用户和车辆'
PRINT ''

-- ============================================
-- 插入学生用户和车辆（3人）
-- ============================================
SET @Counter = 4
WHILE @Counter <= 6
BEGIN
    SET @UserID = @Counter
    SET @UserName = '学生' + RIGHT('000' + CAST(@Counter AS VARCHAR(3)), 3)
    SET @UserType = '学生'
    SET @UserPhone = '139' + RIGHT('00000000' + CAST(@Counter AS VARCHAR(8)), 8)
    SET @CphID = '闽B' + RIGHT('00000' + CAST(@Counter AS VARCHAR(5)), 5)

    -- 插入学生用户
    EXEC proc_InsertUser
        @UserID = @UserID,
        @UserName = @UserName,
        @UserType = @UserType,
        @UserPhone = @UserPhone,
        @CreditScore = 100

    -- 插入学生车辆
    EXEC proc_InsertVehicle
        @CphID = @CphID,
        @ClType = '学生',
        @UserID = @UserID

    SET @Counter = @Counter + 1
END

PRINT '已插入3个学生用户和车辆'
PRINT ''

-- ============================================
-- 插入访客用户和车辆（3人）
-- ============================================
SET @Counter = 7
WHILE @Counter <= 9
BEGIN
    SET @UserID = @Counter
    SET @UserName = '访客' + RIGHT('000' + CAST(@Counter AS VARCHAR(3)), 3)
    SET @UserType = '访客'
    SET @UserPhone = '137' + RIGHT('00000000' + CAST(@Counter AS VARCHAR(8)), 8)
    SET @CphID = '闽C' + RIGHT('00000' + CAST(@Counter AS VARCHAR(5)), 5)

    -- 插入访客用户
    EXEC proc_InsertUser
        @UserID = @UserID,
        @UserName = @UserName,
        @UserType = @UserType,
        @UserPhone = @UserPhone,
        @CreditScore = 100

    -- 插入访客车辆
    EXEC proc_InsertVehicle
        @CphID = @CphID,
        @ClType = '访客',
        @UserID = @UserID

    SET @Counter = @Counter + 1
END

PRINT '已插入3个访客用户和车辆'
PRINT ''

-- ============================================
-- 插入公务车辆（3辆）
-- ============================================
SET @Counter = 10
WHILE @Counter <= 12
BEGIN
    SET @ClType = '公务车辆'
    SET @CphID = '闽D' + RIGHT('00000' + CAST(@Counter AS VARCHAR(5)), 5)

    -- 插入公务车辆（不需要用户）
    EXEC proc_InsertVehicle
        @CphID = @CphID,
        @ClType = @ClType,
        @UserID = NULL

    SET @Counter = @Counter + 1
END

PRINT '已插入3辆公务车辆'
PRINT ''

-- ============================================
-- 插入特殊车辆（3辆）
-- ============================================
SET @Counter = 13
WHILE @Counter <= 15
BEGIN
    SET @ClType = '特殊车辆'
    SET @CphID = '闽E' + RIGHT('00000' + CAST(@Counter AS VARCHAR(5)), 5)

    -- 插入特殊车辆（不需要用户）
    EXEC proc_InsertVehicle
        @CphID = @CphID,
        @ClType = @ClType,
        @UserID = NULL

    SET @Counter = @Counter + 1
END

PRINT '已插入3辆特殊车辆'
PRINT ''

-- ============================================
-- 显示插入结果
-- ============================================
PRINT '===================================='
PRINT '数据插入完成！'
PRINT '===================================='
PRINT ''

PRINT '用户统计：'
SELECT UserType AS 用户类型, COUNT(*) AS 用户数量
FROM FjutUser
GROUP BY UserType
ORDER BY UserType

PRINT ''
PRINT '车辆统计：'
SELECT ClType AS 车辆类型, COUNT(*) AS 车辆数量
FROM Clgl
GROUP BY ClType
ORDER BY ClType

PRINT ''
PRINT '各类型用户拥有的车辆数量：'
SELECT u.UserType AS 用户类型, COUNT(c.CphID) AS 车辆数量
FROM FjutUser u
LEFT JOIN Clgl c ON u.UserID = c.UserID
GROUP BY u.UserType
ORDER BY u.UserType

PRINT ''
PRINT '测试数据插入完成！'
GO