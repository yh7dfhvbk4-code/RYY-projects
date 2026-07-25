USE fjutspace
GO

-- 区域车位统计视图：统计每个区域的车位总数和空闲车位数
CREATE VIEW vw_AreaParkingStats AS
SELECT 
    Area,
    COUNT(*) AS TotalSpaces,
    SUM(CASE WHEN Status = '空闲' THEN 1 ELSE 0 END) AS AvailableSpaces,
    SUM(CASE WHEN Status = '占用' THEN 1 ELSE 0 END) AS OccupiedSpaces,
    SUM(CASE WHEN Status = '预留' THEN 1 ELSE 0 END) AS ReservedSpaces,
    SUM(CASE WHEN Status = '维修中' THEN 1 ELSE 0 END) AS MaintenanceSpaces
FROM Cwgl
GROUP BY Area
GO

-- 车位类型空闲统计视图：统计每种车位类型的空闲车位数
CREATE VIEW vw_TypeAvailableStats AS
SELECT 
    ct.TypeID,
    ct.TypeName,
    COUNT(cw.CwID) AS TotalSpaces,
    SUM(CASE WHEN cw.Status = '空闲' THEN 1 ELSE 0 END) AS AvailableSpaces,
    SUM(CASE WHEN cw.Status = '占用' THEN 1 ELSE 0 END) AS OccupiedSpaces,
    SUM(CASE WHEN cw.Status = '预留' THEN 1 ELSE 0 END) AS ReservedSpaces,
    SUM(CASE WHEN cw.Status = '维修中' THEN 1 ELSE 0 END) AS MaintenanceSpaces
FROM CwType ct
LEFT JOIN Cwgl cw ON ct.TypeID = cw.TypeID
GROUP BY ct.TypeID, ct.TypeName
GO

-- 区域车位类型综合统计视图：统计每个区域每种车位类型的空闲车位数
CREATE VIEW vw_AreaTypeStats AS
SELECT 
    cw.Area,
    ct.TypeID,
    ct.TypeName,
    COUNT(*) AS TotalSpaces,
    SUM(CASE WHEN cw.Status = '空闲' THEN 1 ELSE 0 END) AS AvailableSpaces,
    SUM(CASE WHEN cw.Status = '占用' THEN 1 ELSE 0 END) AS OccupiedSpaces,
    SUM(CASE WHEN cw.Status = '预留' THEN 1 ELSE 0 END) AS ReservedSpaces,
    SUM(CASE WHEN cw.Status = '维修中' THEN 1 ELSE 0 END) AS MaintenanceSpaces
FROM Cwgl cw
INNER JOIN CwType ct ON cw.TypeID = ct.TypeID
GROUP BY cw.Area, ct.TypeID, ct.TypeName
GO
