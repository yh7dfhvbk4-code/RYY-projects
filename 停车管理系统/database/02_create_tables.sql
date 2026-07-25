
USE fjutspace
GO

-- 用户表
CREATE TABLE FjutUser (
    UserID INT NOT NULL PRIMARY KEY, -- 工号/学号/访客编号
    UserName NVARCHAR(50) NOT NULL,
    UserType NVARCHAR(20) NOT NULL CHECK (UserType IN ('教职工', '学生', '访客')),
    UserPhone NVARCHAR(20),
    CreditScore INT DEFAULT 100
    )
GO

-- 车辆信息表
CREATE TABLE Clgl (
    CphID NVARCHAR(20) PRIMARY KEY,
    ClType NVARCHAR(20) CHECK (ClType IN ('教职工', '学生', '访客', '公务车辆', '特殊车辆')),
    UserID INT FOREIGN KEY REFERENCES FjutUser(UserID) 
)
GO

-- 空闲车位类型数量表
CREATE TABLE CwType (
    TypeID INT PRIMARY KEY,
    TypeName NVARCHAR(20) CHECK (TypeName IN ('公务车位', '固定车位', '临时车位', '充电桩')),
    CwSL INT NOT NULL DEFAULT 0
)
GO

-- 车位表
CREATE TABLE Cwgl (
    CwID INT PRIMARY KEY ,
    Cwbh VARCHAR(20) NOT NULL UNIQUE,
    Area NVARCHAR(20) NOT NULL CHECK (Area IN ('教学区','宿舍区','办公区','生活区')),
    TypeID INT NOT NULL FOREIGN KEY REFERENCES CwType(TypeID),
    Status NVARCHAR(20) NOT NULL DEFAULT '空闲' CHECK (Status IN ('空闲','占用','预留','维修中'))
)
GO

-- 车位预约表
CREATE TABLE ParkingReservations (
    ReservationID INT PRIMARY KEY,
    UserID INT FOREIGN KEY REFERENCES FjutUser(UserID),
    TypeID INT FOREIGN KEY REFERENCES CwType(TypeID),
    CwID INT FOREIGN KEY REFERENCES Cwgl(CwID),
    CphID NVARCHAR(20) FOREIGN KEY REFERENCES Clgl(CphID),
    StartTime DATETIME NOT NULL,
    EndTime DATETIME NOT NULL,
    Purpose NVARCHAR(200),
    Status NVARCHAR(20) CHECK (Status IN ('待审批', '已批准', '已使用', '已取消', '违约'))
)
GO

-- 车辆入场记录表
CREATE TABLE InSpace (
    InID INT PRIMARY KEY,
    CphID NVARCHAR(20) NOT NULL FOREIGN KEY REFERENCES Clgl(CphID),
    InTime DATETIME DEFAULT GETDATE(),
    InGate NVARCHAR(50),
    CwID INT FOREIGN KEY REFERENCES Cwgl(CwID),
    ReservationID INT FOREIGN KEY REFERENCES ParkingReservations(ReservationID)
)
GO

-- 车辆出场记录表
CREATE TABLE OutSpace (
    OutID INT PRIMARY KEY,
    InID INT FOREIGN KEY REFERENCES InSpace(InID),
    OutTime DATETIME DEFAULT GETDATE(),
    OutGate NVARCHAR(50),
    ParkingHours DECIMAL(10,2), -- 停车时长
    ParkingFee DECIMAL(10,2),
    PayStatus NVARCHAR(20) CHECK (PayStatus IN ('免费','已支付', '未支付', '异常'))
)
GO
