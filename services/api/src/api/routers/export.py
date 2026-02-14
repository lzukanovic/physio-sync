"""Export endpoints — stub for CSV/HDF5 export."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/{recording_id}/csv")
async def export_csv(recording_id: int):
    # TODO: implement CSV export
    return {"status": "not_implemented", "recording_id": recording_id}


@router.get("/{recording_id}/hdf5")
async def export_hdf5(recording_id: int):
    # TODO: implement HDF5 export
    return {"status": "not_implemented", "recording_id": recording_id}
