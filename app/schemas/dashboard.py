from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    totalEmployees: int
    totalProjects: int
    activeProjects: int
    pendingInvitations: int
    pendingTimesheets: int
    approvedTimesheets: int
    rejectedTimesheets: int


class ProjectUtilizationResponse(BaseModel):
    project: str
    hours: Decimal


class EmployeeUtilizationResponse(BaseModel):
    employee: str
    assignedProjects: int
    loggedHours: Decimal
    expectedHours: Decimal
    utilization: Decimal
    status: str


class RecentTimesheetResponse(BaseModel):
    id: str
    employee: str
    week: str
    hours: Decimal
    status: str


class RecentEmployeeResponse(BaseModel):
    name: str
    role: str
    status: str
    createdDate: date


class UpcomingHolidayResponse(BaseModel):
    name: str
    date: date


class MyDashboardResponse(BaseModel):
    assignedProjects: int
    currentWeekHours: Decimal
    currentTimesheetStatus: Optional[str]
    recentTimesheet: Optional[RecentTimesheetResponse]
    upcomingHolidays: list[UpcomingHolidayResponse]
