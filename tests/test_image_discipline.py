from agewell.editorial import (
    ImageBrief,
    _sanitize_search_queries,
    candidate_passes_discipline,
    deterministic_select_image,
)


def test_sanitize_search_queries_strips_traps_and_deduplicates():
    queries = _sanitize_search_queries(
        (
            "active adult everyday life",
            "nutritional biochemistry scientist liquid chromatography vial",
            "olive oil fresh vegetables mediterranean",
        ),
        "Mediterranean diet may boost tiny proteins that protect the heart and brain",
        "metabolic health",
    )
    assert len(queries) == 3
    assert len(set(q.lower() for q in queries)) == 3
    assert all("active adult everyday life" not in q.lower() for q in queries)
    assert all("liquid chromatography" not in q.lower() for q in queries)
    assert "olive oil fresh vegetables mediterranean" in [q.lower() for q in queries]


def test_candidate_passes_discipline_rejects_cosmetic_and_metaphor_traps():
    # Cosmetic dropper bottle trap
    passed, _, reason = candidate_passes_discipline(
        {
            "candidate_id": "Unsplash:IRM9qgZdlW0",
            "alt": "woman wearing white lab coat holding brown bottle and glass tube",
            "tags": ("cosmetics", "bottle"),
            "creator": "Bee Naturalles",
            "creator_url": "https://unsplash.com/@beenaturalles",
        },
        category="metabolic health",
        source_title="Mediterranean diet may boost tiny proteins",
        headline="Mitochondrial Microproteins Link Mediterranean Diet to Cellular Resilience",
    )
    assert passed is False
    assert "beenaturalles" in reason.lower() or "bottle" in reason.lower() or "cosmetic" in reason.lower()

    # Metaphor trap: "information highway" -> woman driving car in brain health
    passed_car, _, reason_car = candidate_passes_discipline(
        {
            "candidate_id": "Pexels:123",
            "alt": "Side profile of a woman driving with a focus on her face in a car interior",
            "tags": ("car", "driving"),
        },
        category="brain health",
        source_title="Brain imaging reveals how an information hub integrates signals",
        headline="Brain imaging reveals how an information hub integrates signals",
    )
    assert passed_car is False
    assert "driving" in reason_car.lower() or "car interior" in reason_car.lower()

    # Forest balcony trap on deep sleep brainwave story
    passed_balcony, _, _ = candidate_passes_discipline(
        {
            "candidate_id": "Unsplash:PJziBblhxUo",
            "alt": "Barefoot woman stands on wooden balcony overlooking a forest",
            "tags": ("forest", "balcony"),
        },
        category="brain health",
        source_title="Scientists discover mysterious lonely brain waves linked to memory loss",
        headline="Broken Signals in Deep Sleep: How Lonely Brain Waves Reveal Hidden Memory Loss",
    )
    assert passed_balcony is False


def test_deterministic_select_image_picks_on_theme_candidate():
    brief = ImageBrief(
        editorial_intent="Show brain imaging research.",
        subject="doctors examining brain MRI scan",
        setting="neuroscience clinic",
        mood="focused, analytical, calm",
        composition="landscape",
        avoid=("driving", "fashion"),
        search_queries=("neuroscience researcher brain scan", "scientist microscope laboratory", "medical imaging monitor"),
    )
    candidates = [
        {
            "candidate_id": "Unsplash:bad1",
            "alt": "Senior woman posing in a black leather jacket with soft lighting indoors",
            "tags": ("portrait", "fashion"),
        },
        {
            "candidate_id": "Unsplash:good1",
            "alt": "Two doctors examining a brain mri scan together in a laboratory",
            "tags": ("brain", "mri", "medical", "research"),
        },
    ]
    review = deterministic_select_image(
        candidates,
        category="brain health",
        source_title="Scientists discover mysterious lonely brain waves linked to memory loss",
        headline="Broken Signals in Deep Sleep: How Lonely Brain Waves Reveal Hidden Memory Loss",
        image_brief=brief,
    )
    assert review.selected_candidate_id == "Unsplash:good1"
    assert review.metadata_status == "approved"
    assert review.score >= 75
