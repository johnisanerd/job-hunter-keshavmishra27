import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.modules.fetchers.apify_fetcher import ApifyWellfoundFetcher


# Dataset items shaped like johnvc/wellfound-jobs-api output: two job rows,
# then the error row and the free-tier notice row the Actor can push instead.
ACTOR_ITEMS = [
    {
        "result_type": "job",
        "id": "4400001",
        "title": "Machine Learning Intern",
        "slug": "machine-learning-intern",
        "primaryRoleTitle": "Machine Learning Engineer",
        "description": "### About the role\nBuild Python data pipelines for our ranking models.",
        "compensationRaw": "₹6L – ₹12L",
        "jobType": "internship",
        "remote": False,
        "locationNames": ["Bengaluru"],
        "acceptedRemoteLocationNames": [],
        "autoPosted": False,
        "company": {"id": "900001", "name": "Example Labs", "slug": "example-labs", "stage": "early_stage"},
        "url": "https://wellfound.com/jobs/4400001-machine-learning-intern",
        "postedAt": "2026-08-17T18:13:08+00:00",
        "searchContext": {"location": "india", "page": 1},
        "scrapedAt": "2026-10-24T09:00:00+00:00",
    },
    {
        "result_type": "job",
        "id": "4400002",
        "title": "Data Engineering Intern",
        "slug": "data-engineering-intern",
        "primaryRoleTitle": "Data Engineer",
        "description": "Work on our Python ETL stack.",
        "compensationRaw": "$30k – $40k",
        "salaryMin": 30000.0,
        "salaryMax": 40000.0,
        "salaryCurrency": "USD",
        "jobType": "internship",
        "remote": True,
        "remoteKind": "REMOTE_ONLY",
        "locationNames": ["North Carolina"],
        "acceptedRemoteLocationNames": ["India"],
        "company": {"id": "900002", "name": "Sample Data Co", "slug": "sample-data-co"},
        "url": "https://wellfound.com/jobs/4400002-data-engineering-intern",
        "postedAt": "2026-08-13T15:45:00+00:00",
        "searchContext": {"location": "india", "page": 1},
        "scrapedAt": "2026-10-24T09:00:00+00:00",
    },
    {
        "result_type": "error",
        "error_message": "The search pages loaded, but no job matched the filters you set.",
        "error_type": "NoMatchingJobs",
        "fetched_at": "2026-10-24T09:00:00+00:00",
    },
    {
        "free_tier_notice": True,
        "notice": "free_tier_limit_reached",
        "message": "Free monthly allowance reached for this Actor.",
    },
]


@pytest.fixture
def fetcher(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    return ApifyWellfoundFetcher()


def _fetch(fetcher, keywords, location=""):
    actor_cls = type(fetcher.client.actor(ApifyWellfoundFetcher.ACTOR_ID))
    dataset_cls = type(fetcher.client.dataset("dataset-1"))
    # autospec checks each call against the installed apify-client signature.
    with patch.object(actor_cls, "call", autospec=True, return_value={"defaultDatasetId": "dataset-1"}) as mock_call:
        with patch.object(dataset_cls, "list_items", autospec=True, return_value=SimpleNamespace(items=ACTOR_ITEMS)):
            with patch.object(fetcher.client, "actor", wraps=fetcher.client.actor) as mock_actor:
                results = asyncio.run(fetcher.fetch(keywords, location=location))
    return results, mock_actor, mock_call


def test_wellfound_fetcher_maps_actor_output(fetcher):
    results, mock_actor, mock_call = _fetch(fetcher, ["machine learning"])

    mock_actor.assert_called_with("johnvc/wellfound-jobs-api")
    assert mock_call.call_count == 1
    assert mock_call.call_args.kwargs["run_input"] == {
        "keyword": "machine learning",
        "locations": ["India"],
        "maxItems": 30,
    }

    # The error row and the notice row have no title, so they are skipped.
    assert len(results) == 2
    onsite, remote = results

    assert onsite.title == "Machine Learning Intern"
    assert onsite.company == "Example Labs"
    assert onsite.location == "Bengaluru"
    assert onsite.apply_link == "https://wellfound.com/jobs/4400001-machine-learning-intern"
    assert onsite.description == (
        "Salary: ₹6L – ₹12L | ### About the role\nBuild Python data pipelines for our ranking models."
    )
    assert onsite.source == "Wellfound"
    assert onsite.internship_type == "Internship"
    assert onsite.extra == {}

    assert remote.company == "Sample Data Co"
    assert remote.location == "North Carolina"
    assert remote.description == "Salary: $30k – $40k | Work on our Python ETL stack."
    assert remote.extra == {"mode": "remote"}


def test_wellfound_fetcher_searches_first_two_keywords(fetcher):
    results, _, mock_call = _fetch(fetcher, ["python", "web development", "react"], location="Remote")

    assert [c.kwargs["run_input"] for c in mock_call.call_args_list] == [
        {"keyword": "python", "locations": ["Remote"], "maxItems": 30},
        {"keyword": "web development", "locations": ["Remote"], "maxItems": 30},
    ]
    assert len(results) == 4
