"""
Addresses router — multi-address CRUD for authenticated customer.
"""
import uuid
from fastapi import APIRouter, status
from app.dependencies import CurrentUser, AddrSvc
from app.schemas.address import AddressResponse, CreateAddressRequest, UpdateAddressRequest

router = APIRouter(prefix="/api/v1/addresses", tags=["Addresses"])


@router.get("", response_model=list[AddressResponse], summary="List my addresses")
async def list_addresses(current_user: CurrentUser, addr_svc: AddrSvc) -> list[AddressResponse]:
    return await addr_svc.list_addresses(current_user.id)


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED,
             summary="Add a new address")
async def create_address(
    body: CreateAddressRequest, current_user: CurrentUser, addr_svc: AddrSvc,
) -> AddressResponse:
    return await addr_svc.create_address(current_user.id, body)


@router.patch("/{address_id}", response_model=AddressResponse, summary="Update an address")
async def update_address(
    address_id: uuid.UUID, body: UpdateAddressRequest,
    current_user: CurrentUser, addr_svc: AddrSvc,
) -> AddressResponse:
    return await addr_svc.update_address(current_user.id, address_id, body)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete an address")
async def delete_address(
    address_id: uuid.UUID, current_user: CurrentUser, addr_svc: AddrSvc,
) -> None:
    await addr_svc.delete_address(current_user.id, address_id)


@router.post("/{address_id}/set-default", response_model=AddressResponse,
             summary="Set address as default")
async def set_default(
    address_id: uuid.UUID, current_user: CurrentUser, addr_svc: AddrSvc,
) -> AddressResponse:
    return await addr_svc.set_default(current_user.id, address_id)
