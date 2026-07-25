USE fjutspace
GO

-- ============================================
-- 创建触发器：更新车位类型数量表
-- ============================================

-- 触发器1：当车位状态改变时，自动更新对应类型的车位数量
CREATE TRIGGER tri_UpdateCwTypeCount
ON Cwgl
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    -- 声明变量
    DECLARE @TypeID INT
    DECLARE @OldStatus NVARCHAR(20)
    DECLARE @NewStatus NVARCHAR(20)

    -- 如果是更新操作，获取状态变化
    IF EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
    BEGIN
        -- 处理每个更新的记录
        DECLARE update_cursor CURSOR FOR
        SELECT i.TypeID, d.Status AS OldStatus, i.Status AS NewStatus
        FROM inserted i
        INNER JOIN deleted d ON i.CwID = d.CwID

        OPEN update_cursor
        FETCH NEXT FROM update_cursor INTO @TypeID, @OldStatus, @NewStatus

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- 如果状态从空闲变为非空闲，减少空闲数量
            IF @OldStatus = '空闲' AND @NewStatus <> '空闲'
            BEGIN
                UPDATE CwType
                SET CwSL = CwSL - 1
                WHERE TypeID = @TypeID
            END
            -- 如果状态从非空闲变为空闲，增加空闲数量
            ELSE IF @OldStatus <> '空闲' AND @NewStatus = '空闲'
            BEGIN
                UPDATE CwType
                SET CwSL = CwSL + 1
                WHERE TypeID = @TypeID
            END

            FETCH NEXT FROM update_cursor INTO @TypeID, @OldStatus, @NewStatus
        END

        CLOSE update_cursor
        DEALLOCATE update_cursor
    END
    -- 如果是插入操作
    ELSE IF EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted)
    BEGIN
        DECLARE insert_cursor CURSOR FOR
        SELECT TypeID, Status
        FROM inserted

        OPEN insert_cursor
        FETCH NEXT FROM insert_cursor INTO @TypeID, @NewStatus

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- 如果插入的车位是空闲状态，增加空闲数量
            IF @NewStatus = '空闲'
            BEGIN
                UPDATE CwType
                SET CwSL = CwSL + 1
                WHERE TypeID = @TypeID
            END

            FETCH NEXT FROM insert_cursor INTO @TypeID, @NewStatus
        END

        CLOSE insert_cursor
        DEALLOCATE insert_cursor
    END
    -- 如果是删除操作
    ELSE IF NOT EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
    BEGIN
        DECLARE delete_cursor CURSOR FOR
        SELECT TypeID, Status
        FROM deleted

        OPEN delete_cursor
        FETCH NEXT FROM delete_cursor INTO @TypeID, @OldStatus

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- 如果删除的车位是空闲状态，减少空闲数量
            IF @OldStatus = '空闲'
            BEGIN
                UPDATE CwType
                SET CwSL = CwSL - 1
                WHERE TypeID = @TypeID
            END

            FETCH NEXT FROM delete_cursor INTO @TypeID, @OldStatus
        END

        CLOSE delete_cursor
        DEALLOCATE delete_cursor
    END
END
GO

-- ============================================
-- 存储过程：初始化车位类型数量表
-- ============================================
CREATE PROCEDURE proc_InitCwTypeCount
AS
BEGIN
    SET NOCOUNT ON;

    -- 先清空所有类型的数量
    UPDATE CwType SET CwSL = 0

    -- 重新计算每种类型的空闲车位数量
    UPDATE ct
    SET ct.CwSL = (
        SELECT COUNT(*)
        FROM Cwgl c
        WHERE c.TypeID = ct.TypeID AND c.Status = '空闲'
    )
    FROM CwType ct

    PRINT '车位类型数量表初始化完成！'
END
GO

PRINT '触发器和存储过程创建成功！'
GO