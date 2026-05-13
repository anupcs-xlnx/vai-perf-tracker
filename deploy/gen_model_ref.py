#!/usr/bin/env python3
"""Generate model-ref.html — a personal reference page with cards for every tracked model.

Usage:
    python deploy/gen_model_ref.py [OUTPUT_DIR]
"""
from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "dashboard"

_BG     = "#0d0d0d"
_CARD   = "#161616"
_CARD2  = "#1a1a1a"
_BORDER = "#2a2a2a"
_TEXT   = "#e0e0e0"
_MUTED  = "#9d9fa2"
_GOLD   = "#c1a968"
_TEAL   = "#00c2de"

# Each entry: (friendly_name, customer, arch_type, customer_color, description, use_cases, ref)
# customer_color: hex for the customer badge
MODELS = [
    # ── Anduril ──────────────────────────────────────────────────────────────
    (
        "Anduril YOLOX-s",
        "Anduril",
        "CNN · Anchor-free detection",
        "#b45309",
        "YOLOX-Small is the compact tier of the YOLOX family, a high-performance "
        "anchor-free object detector built on a CSPDarkNet backbone with a decoupled "
        "classification/regression head and SimOTA dynamic label assignment. "
        "Achieves 40.5% COCO mAP at real-time speed, making it the preferred choice "
        "when latency is the primary constraint.",
        ["Real-time 2D object detection", "Edge / embedded deployment",
         "Defense & security surveillance", "Low-latency inference on VEK385"],
        "arXiv:2107.08430 · Megvii",
    ),
    (
        "Anduril YOLOX-m",
        "Anduril",
        "CNN · Anchor-free detection",
        "#b45309",
        "YOLOX-Medium sits between YOLOX-s and YOLOX-l, trading a modest latency "
        "increase for improved accuracy (46.9% COCO mAP). Uses the same decoupled "
        "head and MixUp/Mosaic augmentation pipeline. On VEK385, it is the balanced "
        "operating point for Anduril's multi-object tracking pipeline.",
        ["Multi-object tracking in complex scenes", "Defense situational awareness",
         "Balanced accuracy vs. latency trade-off"],
        "arXiv:2107.08430 · Megvii",
    ),
    (
        "Anduril YOLOX-l 640px",
        "Anduril",
        "CNN · Anchor-free detection",
        "#b45309",
        "YOLOX-Large at 640×640 input resolution. Significantly wider and deeper "
        "than YOLOX-m (50.1% COCO mAP). Anduril uses this variant where accuracy "
        "on medium-range targets outweighs the latency budget of the smaller models.",
        ["High-accuracy object detection at 640px", "Defense target classification",
         "Multi-scale detection pipeline stage"],
        "arXiv:2107.08430 · Megvii",
    ),
    (
        "Anduril YOLOX-l 1280px",
        "Anduril",
        "CNN · Anchor-free detection",
        "#b45309",
        "YOLOX-Large run at 1280×1280 input resolution (YOLOX-x model weights). "
        "The doubled input resolution dramatically improves detection of small and "
        "distant objects at the cost of ~9× more pixels to process. This is Anduril's "
        "high-fidelity mode for long-range target detection.",
        ["Long-range / small-target detection", "High-resolution surveillance",
         "Defense ISR (Intelligence, Surveillance, Reconnaissance)"],
        "arXiv:2107.08430 · Megvii",
    ),
    # ── Autoware ─────────────────────────────────────────────────────────────
    (
        "EgoLanes",
        "Autoware",
        "CNN · Semantic segmentation",
        "#065f46",
        "EgoLanes is a lightweight lane-boundary segmentation network from the "
        "Autoware Foundation, designed to label a front-camera frame into ego-left "
        "lane, ego-right lane, other markings, and background in real time. "
        "The EgoLanes Lite variant reduces compute from ~119 GOPs to ~6.1 GOPs "
        "(~20× reduction) while preserving accuracy under nighttime and rain conditions. "
        "It dynamically updates lane assignments during active lane-change maneuvers.",
        ["Lane Departure Warning (LDW)", "Lane Keep Assist (LKA)",
         "Hands-Free Driving feature support",
         "Open-source Autoware SAE L2 ADAS stack"],
        "Autoware Foundation · EgoLanes Lite",
    ),
    # ── SICK ─────────────────────────────────────────────────────────────────
    (
        "RAFT-Stereo",
        "SICK",
        "CNN + GRU · Dense stereo depth",
        "#1e3a5f",
        "RAFT-Stereo adapts the RAFT optical-flow architecture to stereo matching. "
        "A CNN feature encoder builds a 3D epipolar correlation pyramid; a multi-level "
        "GRU iteratively refines a dense disparity field from coarse to fine resolution. "
        "It ranked #1 on the Middlebury stereo leaderboard and generalizes strongly "
        "across datasets without retraining, a key property for industrial deployment.",
        ["Dense metric depth estimation from stereo cameras",
         "3D environment sensing for industrial robots",
         "Logistics automation and bin picking",
         "Machine vision for quality inspection"],
        "arXiv:2109.07547 · Princeton NLP",
    ),
    # ── Wayve ────────────────────────────────────────────────────────────────
    (
        "Wayve ViT s256 d1024",
        "Wayve",
        "Transformer · ViT encoder",
        "#4c1d95",
        "A Vision Transformer encoder processing 256 image patches at embedding "
        "dimension 1024. Batch size 2 enables parallel encoding of two camera "
        "views. This is the smallest (fastest) of Wayve's four encoder variants, "
        "suited for lower-resolution or near-field camera feeds in their surround-view "
        "autonomous driving perception backbone.",
        ["Multi-camera visual feature extraction (AV perception)",
         "Near-field or lower-resolution camera processing",
         "Wayve end-to-end AV system backbone",
         "Token embeddings for downstream detection / segmentation heads"],
        "Wayve LINGO-2, Rig3R",
    ),
    (
        "Wayve ViT s256 d1536",
        "Wayve",
        "Transformer · ViT encoder",
        "#4c1d95",
        "Same 256-patch sequence length as the d1024 variant but with a wider "
        "1536-dimensional embedding. The extra depth provides richer feature "
        "representations at the same spatial resolution, improving downstream "
        "detection and segmentation accuracy for Wayve's perception stack.",
        ["High-fidelity feature extraction from 256-patch crops",
         "Surround-view AV perception backbone",
         "Feeds 3D detection and BEV segmentation heads"],
        "Wayve LINGO-2, Rig3R",
    ),
    (
        "Wayve ViT s512 d1536",
        "Wayve",
        "Transformer · ViT encoder",
        "#4c1d95",
        "Doubles the sequence length to 512 patches (2× spatial resolution vs. s256) "
        "at embedding dimension 1536. Captures finer spatial detail critical for "
        "detecting pedestrians, cyclists, and small road signs at longer range. "
        "The most balanced compute/accuracy point in Wayve's encoder family.",
        ["Medium-to-long-range object detection from high-res cameras",
         "Pedestrian and cyclist detection",
         "Spatial detail for BEV projection and depth estimation"],
        "Wayve LINGO-2, Rig3R",
    ),
    (
        "Wayve ViT s1024 d1536",
        "Wayve",
        "Transformer · ViT encoder",
        "#4c1d95",
        "The highest-resolution encoder: 1024 patches (4× the area of s256) at "
        "embedding dimension 1536. Processes the full resolution of each camera "
        "frame to capture fine-grained scene detail. Most computationally expensive "
        "but provides the richest spatial features for Wayve's long-range perception.",
        ["Long-range / high-resolution surround-view perception",
         "Full-frame feature extraction for panoramic cameras",
         "Dense semantic scene understanding for AV planning"],
        "Wayve LINGO-2, Rig3R",
    ),
    # ── General / AMD ────────────────────────────────────────────────────────
    (
        "DINO-nano ViT",
        "General / AMD",
        "Transformer + CNN hybrid · DEIMv2",
        "#374151",
        "DEIMv2-Small using a DINOv3-pretrained ViT-Tiny backbone with a Spatial "
        "Tuning Adapter (STA) — a parallel lightweight CNN that converts ViT's "
        "single-scale output into multi-scale feature maps for real-time DETR-style "
        "object detection. DINOv3 self-supervised pretraining on massive unlabeled "
        "datasets produces features that transfer to detection and segmentation "
        "with minimal fine-tuning.",
        ["General-purpose visual feature extraction",
         "Real-time embedded object detection",
         "Industrial inspection and robotics perception",
         "Foundation model for downstream vision tasks"],
        "DEIMv2 arXiv:2509.20787 · DINOv2 arXiv:2304.07193",
    ),
    (
        "YOLOv8m",
        "General / AMD",
        "CNN · Anchor-free detection",
        "#374151",
        "YOLOv8-Medium from Ultralytics — features a CSPDarkNet backbone with C2f "
        "(Cross-Stage Partial with 2-feature flow) modules, a PAN-FPN neck, and an "
        "anchor-free decoupled detection head with Task-Aligned Assigner. ~25M "
        "parameters, 50.2% COCO mAP. Supports detection, instance segmentation, "
        "pose estimation, and classification within a single unified framework.",
        ["Real-time object detection on edge hardware",
         "Industrial automation and quality control",
         "Smart cameras and ADAS pre-processing",
         "Robotics and embedded AI applications"],
        "Ultralytics YOLOv8 · arXiv:2408.15857",
    ),
    # ── BEVFormer ────────────────────────────────────────────────────────────
    (
        "BEVFormer-tiny (ResNet-50)",
        "Automotive",
        "CNN + Transformer · BEV 3D detection",
        "#1e3a5f",
        "BEVFormer-tiny with a ResNet-50 image backbone. ResNet-50 extracts 2D "
        "multi-scale features from each surround-view camera; a 6-layer Transformer "
        "encoder converts them to a unified Bird's-Eye-View grid using Spatial "
        "Cross-Attention (deformable sampling from all cameras) and Temporal "
        "Self-Attention (fusing the previous BEV frame for motion modeling). "
        "Camera-only 3D detection without LiDAR.",
        ["Camera-only 3D object detection (vehicles, pedestrians, cyclists)",
         "Surround-view ADAS for cost-constrained platforms",
         "Bird's-Eye-View scene representation",
         "LiDAR-free autonomous driving perception"],
        "BEVFormer arXiv:2203.17270 · ECCV 2022",
    ),
    (
        "BEVFormer-tiny (Transformer)",
        "Automotive",
        "Transformer · BEV 3D detection",
        "#1e3a5f",
        "BEVFormer-tiny with a Swin-Transformer-Tiny image backbone replacing "
        "ResNet-50. The hierarchical ViT backbone captures richer global context "
        "through self-attention at multiple scales, typically gaining ~1–2% NDS "
        "over the CNN backbone. The BEV encoder (spatial + temporal cross-attention) "
        "and task heads are otherwise identical.",
        ["Higher-quality BEV feature extraction vs. CNN backbone",
         "Camera-only 3D detection with improved orientation estimation",
         "Surround-view AV perception where accuracy > latency budget",
         "Transformer-first autonomous driving stacks"],
        "BEVFormer arXiv:2203.17270 · ECCV 2022",
    ),
    # ── Subaru ───────────────────────────────────────────────────────────────
    (
        "Asura (Subaru EyeSight)",
        "Subaru",
        "CNN · Multi-task (det + seg)",
        "#7c2d12",
        "SUBARU ASURA Net is a proprietary multi-task CNN with a shared backbone "
        "feeding approximately 20 task-specific heads, performing simultaneous "
        "object detection and semantic segmentation (drivable-area labeling) "
        "in a single forward pass. Trained on Google Cloud with NVIDIA A100s, "
        "deployed on AMD Vitis AI hardware. Powers Subaru's next-generation "
        "EyeSight ADAS suite, part of Subaru's zero-fatality-by-2030 initiative.",
        ["Simultaneous object detection + drivable-area segmentation",
         "Subaru EyeSight ADAS (Lane Keep, Adaptive Cruise, Pre-Collision Braking)",
         "Real-time multi-task inference on automotive-grade hardware",
         "Stereo camera front-facing perception"],
        "Next Platform · Subaru EyeSight AI (2024)",
    ),
    (
        "Garuda (Subaru EyeSight)",
        "Subaru",
        "CNN (internal codename)",
        "#7c2d12",
        "Garuda is an internal Subaru ADAS codename with no public disclosure. "
        "As a companion to Asura Net within the EyeSight stack, it likely addresses "
        "a complementary perception domain — potentially long-range detection, "
        "adverse-weather robustness, or a specialized sub-network for a specific "
        "sensor modality or edge-case scenario within Subaru's multi-model pipeline.",
        ["Subaru EyeSight ADAS companion perception module",
         "Complementary domain to Asura (likely long-range or specialized task)",
         "Deployed alongside Asura on same Vitis AI hardware"],
        "Internal Subaru project — no public reference",
    ),
    (
        "Route (Subaru EyeSight)",
        "Subaru",
        "DNN (internal codename)",
        "#7c2d12",
        "Route is an internal Subaru codename, most likely a motion planning or "
        "trajectory prediction model that consumes the BEV scene representation "
        "output by Asura/Garuda and produces a safe, legal vehicle trajectory "
        "or waypoints. In a typical ADAS stack, route planning sits downstream "
        "of perception and upstream of vehicle control.",
        ["Vehicle trajectory / path planning in ADAS stack",
         "Downstream consumer of Asura/Garuda perception outputs",
         "Waypoint prediction for adaptive cruise and lane keeping",
         "Deployed as part of Subaru EyeSight on Vitis AI"],
        "Internal Subaru project — no public reference",
    ),
    # ── Intuitive Surgical ───────────────────────────────────────────────────
    (
        "TinyDepth",
        "Intuitive Surgical",
        "ViT + CNN hybrid · Monocular depth",
        "#065f46",
        "TinyDepth is a lightweight self-supervised monocular depth estimation "
        "model using a Tiny-ViT hierarchical encoder for multi-scale representation "
        "learning, combined with a multi-scale fusion attention decoder. Only ~6M "
        "parameters; achieves state-of-the-art results on KITTI and NYU benchmarks. "
        "Enables 3D scene understanding from single endoscopic cameras without "
        "stereo or structured-light depth sensors.",
        ["Per-pixel depth estimation from a single endoscopic camera",
         "Surgical robotic 3D scene understanding (da Vinci)",
         "Instrument proximity and tissue depth estimation",
         "Minimally invasive surgery — laproscopic / gastrointestinal / bronchoscopic"],
        "ScienceDirect 2024 · ZYCheng777/TinyDepth",
    ),
    # ── Fujifilm ─────────────────────────────────────────────────────────────
    (
        "DenseNet-161",
        "Fujifilm",
        "CNN · Dense classification",
        "#1e3a5f",
        "DenseNet-161 is a 161-layer Densely Connected Convolutional Network where "
        "every layer receives feature maps from all preceding layers and passes to "
        "all subsequent layers (L(L+1)/2 connections). Growth rate k=48 produces "
        "2,208 output features. Dense connectivity eliminates vanishing gradients "
        "and enables strong feature reuse with fewer parameters than equivalent "
        "ResNets — particularly valuable for medical image classification where "
        "labeled data is scarce.",
        ["AI-assisted radiological diagnosis (X-ray, CT, endoscopy)",
         "Pneumonia and lung-disease classification from chest X-rays",
         "Gastrointestinal abnormality detection (Fujifilm endoscopy line)",
         "Cancer histopathology image classification"],
        "CVPR 2017 · arXiv:1608.06993",
    ),
    # ── Astemo / Honda ───────────────────────────────────────────────────────
    (
        "PETRv2",
        "Hitachi Astemo",
        "CNN + Transformer · 3D detection",
        "#374151",
        "PETR (Position Embedding TRansformation) v2 is a camera-only 3D object "
        "detector. A CNN backbone extracts 2D features; a 3D Position Encoder "
        "generates per-voxel 3D position embeddings from the camera frustum and "
        "injects them into the 2D features; a DETR-style decoder attends over these "
        "position-aware features with learned object queries. PETRv2 adds temporal "
        "modeling by aligning prior-frame 3D coordinates via ego-motion, then "
        "concatenating with current features. 49.0% mAP and 58.2% NDS on nuScenes (ICCV 2023).",
        ["Camera-only 3D object detection for surround-view ADAS",
         "Temporal 3D detection with ego-motion alignment",
         "Honda ADAS perception without LiDAR",
         "LiDAR-free autonomous driving at Tier-1 supplier scale"],
        "PETRv2 arXiv:2206.01256 · ICCV 2023",
    ),
    (
        "PETRv2 BEV Segmentation",
        "Hitachi Astemo",
        "CNN + Transformer · 3D det + BEV seg",
        "#374151",
        "Multi-task extension of PETRv2 that adds BEV semantic segmentation "
        "alongside 3D detection. BEV-grid segmentation queries are initialized "
        "from fixed anchor points, processed through the same shared DETR "
        "transformer decoder as the detection queries, and decoded into a dense "
        "Bird's-Eye-View semantic map (road, drivable area, lane markings). "
        "The shared decoder adds negligible extra compute over detection-only PETRv2.",
        ["Simultaneous 3D detection + BEV semantic segmentation",
         "Road layout / drivable-area mapping for planning",
         "Lane marking BEV map generation",
         "Honda ADAS unified scene understanding"],
        "PETRv2 arXiv:2206.01256 · ICCV 2023",
    ),
    # ── Focus ─────────────────────────────────────────────────────────────────
    (
        "YOLO11x-seg 1280×1280",
        "Focus",
        "CNN · Instance segmentation",
        "#b45309",
        "Ultralytics YOLO11 Extra-Large instance segmentation variant at 1280×1280 "
        "input resolution. YOLO11 replaces YOLOv8's C3 blocks with C3k2 blocks and "
        "adds attention mechanisms, achieving 22% fewer parameters than YOLOv8m at "
        "equivalent accuracy. The 'x' tier maximizes network width and depth; the "
        "doubled 1280px resolution improves detection of small and densely packed "
        "objects at the cost of higher compute.",
        ["Per-instance pixel-level object mask generation",
         "Industrial defect detection and parts inspection",
         "Robotic pick-and-place requiring exact object boundaries",
         "High-precision segmentation on dense or small-object scenes"],
        "Ultralytics YOLO11 · docs.ultralytics.com/models/yolo11",
    ),
    # ── Kria2 ────────────────────────────────────────────────────────────────
    (
        "YOLO12l",
        "Kria2 / AMD",
        "CNN + Attention · Detection",
        "#374151",
        "YOLO12-Large introduces attention-centric design to the YOLO family: "
        "Area Attention (A²) divides feature maps into horizontal/vertical regions "
        "and applies self-attention within each region for a large receptive field "
        "with manageable complexity; Residual ELAN blocks provide optimization "
        "stability; FlashAttention and removed positional encoding improve inference "
        "speed. Closes the accuracy gap between YOLO-speed CNNs and full Transformer "
        "detectors. Deployed on AMD Kria SOM via Vitis AI.",
        ["High-accuracy embedded object detection on AMD Kria SOM",
         "Industrial robotics and smart camera automation",
         "Edge AI applications requiring attention-level accuracy at YOLO speed",
         "Embedded automotive and factory automation"],
        "YOLO12 arXiv:2502.12524 · NeurIPS 2025",
    ),
]


def _customer_badge(customer: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'border-radius:12px;padding:2px 10px;font-size:0.72rem;font-weight:600;'
        f'white-space:nowrap">{customer}</span>'
    )


def _arch_tag(arch: str) -> str:
    return (
        f'<span style="background:#1e2a33;color:{_TEAL};border:1px solid {_TEAL}33;'
        f'border-radius:4px;padding:1px 8px;font-size:0.70rem;white-space:nowrap">'
        f'{arch}</span>'
    )


def _use_case_chips(use_cases: list[str]) -> str:
    chips = "".join(
        f'<span style="background:#1e1e1e;color:{_MUTED};border:1px solid {_BORDER};'
        f'border-radius:4px;padding:2px 8px;font-size:0.72rem;white-space:nowrap">'
        f'{uc}</span>'
        for uc in use_cases
    )
    return f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">{chips}</div>'


def _model_card(name: str, customer: str, arch: str, ccolor: str,
                description: str, use_cases: list[str], ref: str) -> str:
    return (
        f'<div style="background:{_CARD};border:1px solid {_BORDER};border-radius:10px;'
        f'padding:20px;display:flex;flex-direction:column;gap:10px">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">'
        f'<h2 style="margin:0;color:{_GOLD};font-size:1.05rem;font-weight:700">{name}</h2>'
        f'{_customer_badge(customer, ccolor)}'
        f'</div>'
        f'{_arch_tag(arch)}'
        f'<p style="margin:4px 0 0;color:{_TEXT};font-size:0.88rem;line-height:1.6">{description}</p>'
        f'{_use_case_chips(use_cases)}'
        f'<p style="margin:6px 0 0;color:{_MUTED};font-size:0.72rem;font-style:italic">'
        f'Ref: {ref}</p>'
        f'</div>'
    )


def _card_wrappers() -> str:
    parts = []
    for m in MODELS:
        name, customer, arch, ccolor, desc, use_cases, ref = m
        search_text = " ".join([name, customer, arch, desc] + use_cases + [ref]).lower()
        card_html = _model_card(*m)
        parts.append(
            f'<div class="card-wrap" data-customer="{customer}" '
            f'data-text="{search_text}">{card_html}</div>'
        )
    return "\n".join(parts)


def generate_model_ref(output_dir: Path) -> Path:
    out_path = output_dir / "model-ref.html"

    cards_html = "\n".join(
        _model_card(name, customer, arch, ccolor, desc, use_cases, ref)
        for name, customer, arch, ccolor, desc, use_cases, ref in MODELS
    )

    customer_set = sorted({m[1] for m in MODELS})
    filter_buttons = "".join(
        f'<button onclick="filterCustomer(\'{c}\')" '
        f'style="background:#1e1e1e;color:{_MUTED};border:1px solid {_BORDER};'
        f'border-radius:4px;padding:4px 12px;font-size:0.78rem;cursor:pointer" '
        f'data-customer="{c}">{c}</button>'
        for c in customer_set
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Model Reference — VAI 6.2</title>
  <style>
    :root {{ color-scheme: dark; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: {_BG}; color: {_TEXT}; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ color: {_GOLD}; font-size: 1.6rem; margin: 0 0 4px; }}
    .muted {{ color: {_MUTED}; font-size: 0.88rem; }}
    a {{ color: {_TEAL}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
      gap: 18px;
      margin-top: 24px;
    }}
    .filter-bar {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; align-items:center; }}
    .filter-bar input {{
      background:#1e1e1e; color:{_TEXT}; border:1px solid {_BORDER};
      border-radius:4px; padding:5px 12px; font-size:0.82rem; outline:none;
      min-width:220px;
    }}
    .filter-bar input:focus {{ border-color:{_TEAL}55; }}
    button.active {{
      background:{_TEAL}22 !important;
      color:{_TEAL} !important;
      border-color:{_TEAL}55 !important;
    }}
    .card-wrap.hidden {{ display: none; }}
  </style>
</head>
<body>
  <main>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
      <div>
        <h1>
          <a href="./" title="Back to dashboard"
            style="color:{_MUTED};font-size:1rem;margin-right:10px;vertical-align:middle">&#8592;</a>
          VAI 6.2 Model Reference
        </h1>
        <p class="muted">
          {len(MODELS)} models tracked across {len(customer_set)} customers/partners.
          Personal reference — architecture, use case, and context for each model.
        </p>
      </div>
    </div>

    <div class="filter-bar">
      <input id="search" placeholder="Search models, architectures, use cases…" oninput="applyFilters()">
      <button onclick="filterCustomer('')" class="active" data-customer="">All</button>
      {filter_buttons}
    </div>

    <div class="grid" id="grid">
{_card_wrappers()}
    </div>
  </main>

  <footer style="text-align:center;padding:16px 24px;color:{_MUTED};font-size:0.78rem;
    border-top:1px solid {_BORDER};margin-top:32px;">
    <a href="./">&#8592; Back to Dashboard</a>
    &nbsp;|&nbsp; Internal reference — VAI 6.2 QoR
  </footer>

  <script>
    let activeCustomer = '';

    function filterCustomer(c) {{
      activeCustomer = c;
      document.querySelectorAll('[data-customer] button, .filter-bar button').forEach(b => {{
        b.classList.remove('active');
      }});
      document.querySelectorAll('.filter-bar button').forEach(b => {{
        if (b.dataset.customer === c) b.classList.add('active');
      }});
      applyFilters();
    }}

    function applyFilters() {{
      const q = document.getElementById('search').value.trim().toLowerCase();
      document.querySelectorAll('.card-wrap').forEach(card => {{
        const matchCustomer = !activeCustomer || card.dataset.customer === activeCustomer;
        const matchSearch   = !q || card.dataset.text.includes(q);
        card.classList.toggle('hidden', !(matchCustomer && matchSearch));
      }});
    }}
  </script>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)
    path = generate_model_ref(output_dir)
    print(f"Written: {path}")
