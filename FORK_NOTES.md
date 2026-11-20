# GitRatio pahebatcher fork

This is an independently maintained derivative of [abdullahkhfb/pahebatcher](https://github.com/abdullahkhfb/pahebatcher).

The original source code is distributed under the MIT license. The original copyright notice and `LICENSE` are preserved. This fork is not an official release or endorsement by the upstream maintainer.

## Development policy

- Preserve the working CLI, GUI, search, download, session and watchlist behaviors unless an explicit compatibility change is documented.
- Put reliability and security fixes ahead of cosmetic rewrites.
- Add regression tests for every confirmed bug.
- Keep the original source attribution and identify fork-specific changes in versioned release notes.
- Develop changes on focused feature branches; merge only when unit, visual and packaging checks pass.
- Do not send changes or notifications to the upstream maintainer without appropriate permissions. Share optional suggestions respectfully.

## Early reliability changes

- Use unambiguous episode prefixes when detecting existing MP4 files.
- Exclude empty cached HLS segments from resume-completed indices.
- Add focused regression tests for both cases.

## Planned work (not yet implemented)

1. Validate finished MP4 output with ffprobe and use atomic remux publication.
2. Add playlist fingerprints and per-segment integrity metadata to resume state.
3. Replace eager HLS segment-task allocation with a bounded queue.
4. Bring watchlist and streaming controls into the desktop interface.
5. Add optional anime metadata enrichment, retaining existing source selection logic.
6. Add signed/checksummed release assets and more cross-platform checks.

## Test commands

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

Runtime download and streaming tests require network access and suitable source permissions; ordinary unit tests should not depend on live third-party streaming websites.
