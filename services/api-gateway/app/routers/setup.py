"""Setup wizard router - AI-assisted initial configuration"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class SetupStatus(BaseModel):
    completed: bool = False
    current_step: int = 0
    total_steps: int = 7
    steps_completed: List[str] = []


class NetworkScanRequest(BaseModel):
    subnet: str


class IdentitySourceSetup(BaseModel):
    type: str  # "ad", "ldap", "saml", "oauth", "internal"
    config: dict


class NetworkDesignNL(BaseModel):
    description: str  # Natural language description of network design


@router.get("/status", response_model=SetupStatus)
async def get_setup_status():
    return SetupStatus()


@router.post("/step/{step_number}")
async def complete_step(step_number: int, data: dict = {}):
    return {"step": step_number, "status": "completed", "next_step": step_number + 1}


@router.post("/network-scan")
async def scan_network(req: NetworkScanRequest):
    return {"devices": [], "scan_status": "completed"}


@router.post("/identity-source")
async def setup_identity_source(req: IdentitySourceSetup):
    return {"status": "configured", "users_found": 0}


@router.post("/network-design/generate")
async def generate_network_design(req: NetworkDesignNL):
    return {"vlans": [], "sgts": [], "auth_profiles": [], "explanation": ""}


@router.post("/policies/generate")
async def generate_policies():
    return {"policy_set": None, "rules": [], "explanation": ""}


@router.post("/activate")
async def activate_configuration():
    return {"status": "activated", "tests_passed": 0, "tests_failed": 0}
