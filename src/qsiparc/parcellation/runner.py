"""Run parcellation jobs."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Iterable, List

import nibabel as nib
from nibabel.processing import resample_from_to
from nilearn.image import resample_to_img

from qsiparc.parcellation.jobs import ParcellationConfig, ParcellationJob, ParcellationResult
from qsiparc.parcellation.volume import parcellate_volume


def run_parcellation(
    jobs: Iterable[ParcellationJob] | Dict[str, List[ParcellationJob]], config: ParcellationConfig | None = None
) -> List[ParcellationResult]:
    """Execute parcellation jobs and return results."""

    cfg = config or ParcellationConfig()
    if isinstance(jobs, dict):
        jobs_iterable = [job for group in jobs.values() for job in group]
    else:
        jobs_iterable = list(jobs)
    results: List[ParcellationResult] = []
    resampled_atlases: Dict[str, Path] = {}
    for job in jobs_iterable:
        atlas_img = _maybe_resample_atlas(job, resampled_atlases)
        stats_df = parcellate_volume(
            atlas_path=atlas_img,
            scalar_path=job.scalar.nifti_path,
            metrics=job.metrics,
            lut=job.atlas.lut,
            resample_target=job.resample_target,
            mask=job.mask,
        )
        stats_dict = stats_df.reset_index().set_index("index").to_dict(orient="index")

        output_path = None
        if cfg.output_root:
            output_path = _write_output(cfg.output_root, job, stats_df)

        results.append(ParcellationResult(job=job, stats=stats_dict, table=stats_df, output_path=output_path))
    return results


def _maybe_resample_atlas(job: ParcellationJob, cache: Dict[str, Path]) -> nib.Nifti1Image:
    """Resample atlas once per atlas-scalar grid when targeting data.

    - If target is not data/scalar, return atlas as-is.
    - Cache resampled atlases keyed by atlas+scalar path combo.
    """

    if job.resample_target not in {"scalar", "data"}:
        return nib.load(job.atlas.nifti_path)
    key = f"{job.atlas.nifti_path}:{job.scalar.nifti_path}"
    if key in cache:
        return nib.load(cache[key])
    atlas_img = nib.load(job.atlas.nifti_path)
    scalar_img = nib.load(job.scalar.nifti_path)
    resampled = resample_to_img(atlas_img, scalar_img, interpolation="nearest")
    tmp = NamedTemporaryFile(suffix="_atlas_resampled.nii.gz", delete=False)
    nib.save(resampled, tmp.name)
    cache[key] = Path(tmp.name)
    return resampled


def _write_output(base: Path, job: ParcellationJob, payload) -> Path:
    """Write per-job output to disk using a BIDS-like filename."""

    parts = [f"sub-{job.context.subject_id}"]
    if job.context.session_id:
        parts.append(f"ses-{job.context.session_id}")
    space = job.atlas.space or job.scalar.space
    if space:
        parts.append(f"space-{space}")
    if job.atlas.resolution:
        parts.append(f"res-{job.atlas.resolution}")
    parts.append(f"atlas-{job.atlas.name}")
    parts.append(f"desc-{job.scalar.name}")
    fname = "_".join(parts) + "_parc.tsv"

    dest = base / f"sub-{job.context.subject_id}"
    if job.context.session_id:
        dest = dest / f"ses-{job.context.session_id}"
    # QSIRecon places scalar maps under dwi/; keep the same sub/ses/dwi structure for parcellation tables.
    dest = dest / "dwi"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / fname

    if hasattr(payload, "to_csv"):
        payload.to_csv(path, sep="\t", index=False)
    else:
        import pandas as pd

        df = pd.DataFrame(payload).T.reset_index()
        df.to_csv(path, sep="\t", index=False)
    return path
