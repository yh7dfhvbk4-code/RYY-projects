
USE fjutspace
GO

-- 支付停车费存储过程
-- 根据OutID更新支付状态
CREATE PROCEDURE proc_PayParkingFee
    @OutID INT,
    @PaymentMethod NVARCHAR(50) = '现金',  -- 支付方式：现金、微信、支付宝、银行卡等
    @PaymentTime DATETIME = NULL  -- 支付时间，如果为NULL则使用当前时间
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @PayStatus NVARCHAR(20)
    DECLARE @ParkingFee DECIMAL(10,2)
    DECLARE @CphID NVARCHAR(20)
    DECLARE @InID INT

    -- 检查出场记录是否存在
    IF NOT EXISTS (SELECT 1 FROM OutSpace WHERE OutID = @OutID)
    BEGIN
        RAISERROR('未找到该出场记录', 16, 1)
        RETURN
    END

    -- 获取当前支付状态和费用信息
    SELECT 
        @PayStatus = PayStatus,
        @ParkingFee = ParkingFee,
        @InID = InID
    FROM OutSpace
    WHERE OutID = @OutID

    -- 检查是否已支付
    IF @PayStatus = '已支付'
    BEGIN
        RAISERROR('该记录已支付，请勿重复支付', 16, 1)
        RETURN
    END

    -- 检查是否为免费记录
    IF @PayStatus = '免费'
    BEGIN
        RAISERROR('该记录为免费记录，无需支付', 16, 1)
        RETURN
    END

    -- 获取车牌号
    SELECT @CphID = CphID FROM InSpace WHERE InID = @InID

    -- 如果未指定支付时间，使用当前时间
    IF @PaymentTime IS NULL
        SET @PaymentTime = GETDATE()

    -- 更新支付状态
    UPDATE OutSpace
    SET PayStatus = '已支付'
    WHERE OutID = @OutID

    -- 记录支付日志
    INSERT INTO PaymentLog (
        OutID,
        CphID,
        Amount,
        PaymentMethod,
        PaymentTime,
        Status
    )
    VALUES (
        @OutID,
        @CphID,
        @ParkingFee,
        @PaymentMethod,
        @PaymentTime,
        '成功'
    )

    PRINT '支付成功，车牌: ' + @CphID + '，金额: ' + CAST(@ParkingFee AS NVARCHAR(20)) + '元'
END
GO

-- 批量支付存储过程
-- 支持一次支付多个未支付记录
CREATE PROCEDURE proc_BatchPayParkingFee
    @OutIDs NVARCHAR(MAX)  -- 逗号分隔的OutID列表
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @TotalAmount DECIMAL(10,2) = 0
    DECLARE @SuccessCount INT = 0
    DECLARE @FailedCount INT = 0

    -- 创建临时表存储OutID
    CREATE TABLE #TempOutIDs (OutID INT)

    -- 分割OutID字符串并插入临时表
    DECLARE @Pos INT
    DECLARE @Value NVARCHAR(50)
    DECLARE @Delimiter NVARCHAR(1) = ','

    WHILE LEN(@OutIDs) > 0
    BEGIN
        SET @Pos = CHARINDEX(@Delimiter, @OutIDs)
        IF @Pos = 0
        BEGIN
            SET @Value = @OutIDs
            SET @OutIDs = ''
        END
        ELSE
        BEGIN
            SET @Value = LEFT(@OutIDs, @Pos - 1)
            SET @OutIDs = SUBSTRING(@OutIDs, @Pos + 1, LEN(@OutIDs))
        END

        IF ISNUMERIC(@Value) = 1
            INSERT INTO #TempOutIDs (OutID) VALUES (CAST(@Value AS INT))
    END

    -- 遍历临时表，逐个支付
    DECLARE @CurrentOutID INT
    DECLARE @CurrentFee DECIMAL(10,2)
    DECLARE @CurrentStatus NVARCHAR(20)

    DECLARE payment_cursor CURSOR FOR
        SELECT OutID FROM #TempOutIDs

    OPEN payment_cursor
    FETCH NEXT FROM payment_cursor INTO @CurrentOutID

    WHILE @@FETCH_STATUS = 0
    BEGIN
        -- 获取当前记录状态和费用
        SELECT 
            @CurrentStatus = PayStatus,
            @CurrentFee = ParkingFee
        FROM OutSpace
        WHERE OutID = @CurrentOutID

        -- 如果记录存在且未支付，则执行支付
        IF @CurrentStatus IS NOT NULL AND @CurrentStatus = '未支付'
        BEGIN
            UPDATE OutSpace
            SET PayStatus = '已支付'
            WHERE OutID = @CurrentOutID

            SET @TotalAmount = @TotalAmount + @CurrentFee
            SET @SuccessCount = @SuccessCount + 1
        END
        ELSE
        BEGIN
            SET @FailedCount = @FailedCount + 1
        END

        FETCH NEXT FROM payment_cursor INTO @CurrentOutID
    END

    CLOSE payment_cursor
    DEALLOCATE payment_cursor

    -- 删除临时表
    DROP TABLE #TempOutIDs

    -- 返回结果
    SELECT 
        @SuccessCount AS SuccessCount,
        @FailedCount AS FailedCount,
        @TotalAmount AS TotalAmount

    PRINT '批量支付完成，成功: ' + CAST(@SuccessCount AS NVARCHAR(10)) + 
          '，失败: ' + CAST(@FailedCount AS NVARCHAR(10)) + 
          '，总金额: ' + CAST(@TotalAmount AS NVARCHAR(20)) + '元'
END
GO

-- 获取未支付记录存储过程
CREATE PROCEDURE proc_GetUnpaidRecords
    @CphID NVARCHAR(20) = NULL,  -- 可选：按车牌号筛选
    @StartDate DATETIME = NULL,   -- 可选：开始日期
    @EndDate DATETIME = NULL      -- 可选：结束日期
AS
BEGIN
    SET NOCOUNT ON;

    SELECT 
        o.OutID,
        o.InID,
        o.ParkingHours,
        o.ParkingFee,
        o.OutTime,
        i.CphID,
        i.InTime,
        i.InGate,
        c.ClType
    FROM OutSpace o
    INNER JOIN InSpace i ON o.InID = i.InID
    LEFT JOIN Clgl c ON i.CphID = c.CphID
    WHERE o.PayStatus = '未支付'
    AND (@CphID IS NULL OR i.CphID = @CphID)
    AND (@StartDate IS NULL OR o.OutTime >= @StartDate)
    AND (@EndDate IS NULL OR o.OutTime <= @EndDate)
    ORDER BY o.OutTime DESC
END
GO

-- 获取支付统计信息存储过程
CREATE PROCEDURE proc_GetPaymentStatistics
    @StartDate DATETIME = NULL,   -- 可选：开始日期
    @EndDate DATETIME = NULL      -- 可选：结束日期
AS
BEGIN
    SET NOCOUNT ON;

    -- 如果未指定日期范围，默认查询最近30天
    IF @StartDate IS NULL
        SET @StartDate = DATEADD(DAY, -30, GETDATE())

    IF @EndDate IS NULL
        SET @EndDate = GETDATE()

    -- 总体统计
    SELECT 
        COUNT(*) AS TotalRecords,
        SUM(CASE WHEN PayStatus = '已支付' THEN 1 ELSE 0 END) AS PaidCount,
        SUM(CASE WHEN PayStatus = '未支付' THEN 1 ELSE 0 END) AS UnpaidCount,
        SUM(CASE WHEN PayStatus = '免费' THEN 1 ELSE 0 END) AS FreeCount,
        SUM(ParkingFee) AS TotalAmount,
        SUM(CASE WHEN PayStatus = '已支付' THEN ParkingFee ELSE 0 END) AS PaidAmount,
        SUM(CASE WHEN PayStatus = '未支付' THEN ParkingFee ELSE 0 END) AS UnpaidAmount
    FROM OutSpace
    WHERE OutTime BETWEEN @StartDate AND @EndDate

    -- 按支付状态统计
    SELECT 
        PayStatus,
        COUNT(*) AS Count,
        SUM(ParkingFee) AS TotalAmount
    FROM OutSpace
    WHERE OutTime BETWEEN @StartDate AND @EndDate
    GROUP BY PayStatus
    ORDER BY PayStatus

    -- 按车辆类型统计
    SELECT 
        c.ClType,
        COUNT(*) AS Count,
        SUM(o.ParkingFee) AS TotalAmount,
        SUM(CASE WHEN o.PayStatus = '已支付' THEN o.ParkingFee ELSE 0 END) AS PaidAmount,
        SUM(CASE WHEN o.PayStatus = '未支付' THEN o.ParkingFee ELSE 0 END) AS UnpaidAmount
    FROM OutSpace o
    INNER JOIN InSpace i ON o.InID = i.InID
    INNER JOIN Clgl c ON i.CphID = c.CphID
    WHERE o.OutTime BETWEEN @StartDate AND @EndDate
    GROUP BY c.ClType
    ORDER BY c.ClType
END
GO

-- 创建支付日志表
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[PaymentLog]') AND type in (N'U'))
BEGIN
    CREATE TABLE PaymentLog (
        LogID INT IDENTITY(1,1) PRIMARY KEY,
        OutID INT NOT NULL,
        CphID NVARCHAR(20) NOT NULL,
        Amount DECIMAL(10,2) NOT NULL,
        PaymentMethod NVARCHAR(50) NOT NULL,
        PaymentTime DATETIME NOT NULL,
        Status NVARCHAR(20) NOT NULL,  -- 成功、失败、退款等
        Remark NVARCHAR(200),
        CreateTime DATETIME DEFAULT GETDATE()
    )
END
GO

-- 创建支付日志表的索引
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_PaymentLog_OutID' AND object_id = OBJECT_ID('PaymentLog'))
BEGIN
    CREATE INDEX IX_PaymentLog_OutID ON PaymentLog(OutID)
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_PaymentLog_CphID' AND object_id = OBJECT_ID('PaymentLog'))
BEGIN
    CREATE INDEX IX_PaymentLog_CphID ON PaymentLog(CphID)
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_PaymentLog_PaymentTime' AND object_id = OBJECT_ID('PaymentLog'))
BEGIN
    CREATE INDEX IX_PaymentLog_PaymentTime ON PaymentLog(PaymentTime)
END
GO
