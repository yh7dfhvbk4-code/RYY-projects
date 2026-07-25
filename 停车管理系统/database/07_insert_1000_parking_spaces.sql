USE fjutspace
GO

-- ============================================
-- 插入1000个车位
-- 比例：临时车位：固定车位：公务车位：充电桩 = 10:10:4:1
-- 区域：教学区、宿舍区、办公区、生活区
-- ============================================

-- 插入车位类型数据
IF NOT EXISTS (SELECT 1 FROM CwType WHERE TypeID = 1)
BEGIN
    EXEC proc_InsertCwType @TypeID = 1, @TypeName = '公务车位', @CwSL = 0
    EXEC proc_InsertCwType @TypeID = 2, @TypeName = '固定车位', @CwSL = 0
    EXEC proc_InsertCwType @TypeID = 3, @TypeName = '临时车位', @CwSL = 0
    EXEC proc_InsertCwType @TypeID = 4, @TypeName = '充电桩', @CwSL = 0
    PRINT '车位类型数据插入完成！'
END
ELSE
BEGIN
    PRINT '车位类型数据已存在，跳过插入。'
END
GO

-- 声明变量
DECLARE @CwID INT = 1
DECLARE @Area NVARCHAR(20)
DECLARE @TypeID INT
DECLARE @Cwbh VARCHAR(20)
DECLARE @Counter INT = 1

-- 计算各类型车位数量
-- 总数1000，比例10:10:4:1，共25份
-- 临时车位：1000 * 10/25 = 400
-- 固定车位：1000 * 10/25 = 400
-- 公务车位：1000 * 4/25 = 160
-- 充电桩：1000 * 1/25 = 40

-- 按区域循环插入车位
WHILE @Counter <= 1000
BEGIN
    -- 确定区域（均匀分配到4个区域）
    IF @Counter % 4 = 1
        SET @Area = '教学区'
    ELSE IF @Counter % 4 = 2
        SET @Area = '宿舍区'
    ELSE IF @Counter % 4 = 3
        SET @Area = '办公区'
    ELSE
        SET @Area = '生活区'

    -- 确定车位类型（按比例分配）
    IF @Counter <= 400
        SET @TypeID = 3  -- 临时车位
    ELSE IF @Counter <= 800
        SET @TypeID = 2  -- 固定车位
    ELSE IF @Counter <= 960
        SET @TypeID = 1  -- 公务车位
    ELSE
        SET @TypeID = 4  -- 充电桩

    -- 生成车位编号（格式：区域缩写-序号）
    SET @Cwbh = CASE @Area
        WHEN '教学区' THEN 'JXQ-' + RIGHT('0000' + CAST(@Counter AS VARCHAR(4)), 4)
        WHEN '宿舍区' THEN 'SSQ-' + RIGHT('0000' + CAST(@Counter AS VARCHAR(4)), 4)
        WHEN '办公区' THEN 'BGQ-' + RIGHT('0000' + CAST(@Counter AS VARCHAR(4)), 4)
        WHEN '生活区' THEN 'SHQ-' + RIGHT('0000' + CAST(@Counter AS VARCHAR(4)), 4)
    END

    -- 调用存储过程插入车位
    EXEC proc_InsertParkingSpace
        @CwID = @CwID,
        @Cwbh = @Cwbh,
        @Area = @Area,
        @TypeID = @TypeID,
        @Status = '空闲'

    SET @CwID = @CwID + 1
    SET @Counter = @Counter + 1
END

-- 显示插入结果
PRINT '车位插入完成！'
PRINT '总车位数：1000'
PRINT '各区域车位分布：'
SELECT Area AS 区域, COUNT(*) AS 车位数量
FROM Cwgl
GROUP BY Area
ORDER BY Area

PRINT ''
PRINT '各类型车位分布：'
SELECT t.TypeName AS 车位类型, COUNT(*) AS 车位数量
FROM Cwgl c
INNER JOIN CwType t ON c.TypeID = t.TypeID
GROUP BY t.TypeName
ORDER BY t.TypeName

PRINT ''
PRINT '各区域各类型车位分布：'
SELECT c.Area AS 区域, t.TypeName AS 车位类型, COUNT(*) AS 车位数量
FROM Cwgl c
INNER JOIN CwType t ON c.TypeID = t.TypeID
GROUP BY c.Area, t.TypeName
ORDER BY c.Area, t.TypeName
GO