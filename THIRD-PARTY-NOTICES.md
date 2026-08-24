# Third-party notices

FlareSolverr is distributed under the MIT License (see `LICENSE`). It bundles or depends
on the third-party components below, which carry their own terms. Distributions of this
software in binary form -- including the Docker images -- reproduce these notices to
satisfy those terms.

---

## Scrapling

Used as the browser engine when `BROWSER_ENGINE=scrapling`. Installed as a dependency
from `requirements-scrapling.txt`; no Scrapling source is vendored in this repository.

- Project: https://github.com/D4Vinci/Scrapling
- Author: Karim Shoair
- License: BSD 3-Clause

> BSD 3-Clause License
>
> Copyright (c) 2024, Karim shoair
>
> Redistribution and use in source and binary forms, with or without
> modification, are permitted provided that the following conditions are met:
>
> 1. Redistributions of source code must retain the above copyright notice, this
>    list of conditions and the following disclaimer.
>
> 2. Redistributions in binary form must reproduce the above copyright notice,
>    this list of conditions and the following disclaimer in the documentation
>    and/or other materials provided with the distribution.
>
> 3. Neither the name of the copyright holder nor the names of its
>    contributors may be used to endorse or promote products derived from
>    this software without specific prior written permission.
>
> THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
> AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
> IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
> DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
> FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
> DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
> SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
> CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
> OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
> OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Per clause 3, neither the Scrapling name nor its author's name is used here to endorse
or promote this project. References to Scrapling are factual statements about which
browser engine is in use.

---

## undetected-chromedriver

Vendored in `src/undetected_chromedriver/`, used when `BROWSER_ENGINE=uc` (the default).

- Project: https://github.com/ultrafunkamsterdam/undetected-chromedriver
- Author: UltrafunkAmsterdam
- Vendored version: 3.5.5 (`src/undetected_chromedriver/__init__.py`)
- License upstream: **GPL-3.0** (PyPI `license` field and OSI classifier)

Note for maintainers: the vendored copy in this tree carries attribution but no license
header or license file, so its terms are only discoverable from the upstream project.
This predates the engine work here and is unchanged by it, but a GPL-3.0 component
vendored into an MIT-licensed distribution is worth an explicit decision rather than an
inherited one. Selecting `BROWSER_ENGINE=scrapling` does not remove this code from the
image; only deleting `src/undetected_chromedriver/` would.

---

## Other dependencies

The remaining Python dependencies are listed in `requirements.txt` and
`requirements-scrapling.txt`. Notable transitive components of the Scrapling engine:

| Component | License |
| --------- | ------- |
| Playwright (Python) | Apache-2.0 |
| Patchright (Python) | Apache-2.0 |
| lxml | BSD-3-Clause |
| curl_cffi | MIT |
| browserforge | MIT |
