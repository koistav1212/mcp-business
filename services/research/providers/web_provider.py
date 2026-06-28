import asyncio
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup  # pip install beautifulsoup4

from services.research.base import BaseProvider
from services.knowledge.evidence import ResearchEvidence
from services.knowledge.citation_manager import CitationManager
from services.research.providers.shared_utils import _write_json, BROWSER_HEADERS, logger


class WebProvider(BaseProvider):
    """
    Aggregates technology and architecture intelligence for a company by
    crawling its public web presence and building a structured technology profile.

    Data sources (first pass):
      - Company website (home, /careers, /jobs if present)
      - Linked GitHub org/user (if found on the site)

    Outputs:
      - technology_profile: compact domain-specific categories (e.g., languages, ai_frameworks, cloud)
      - technology_intelligence: broader technology-intel categories (core_platforms,
        programming_languages, frontend_frameworks, backend_frameworks, ai_ml_frameworks,
        cloud_providers, databases, data_engineering, containerization, orchestration,
        ci_cd, monitoring, security, cdn, api_technologies, mobile_technologies, web_servers)
    """

    async def fetch(self, target: Any) -> List[ResearchEvidence]:
        company = self._extract_identifier(target)
        if not company:
            return []

        company_clean = company.strip()
        company_key = company_clean.lower()

        evidence_list: List[ResearchEvidence] = []

        # ------------------------------------------------------------------
        # 1) Discover base URL(s) for crawling
        # ------------------------------------------------------------------
        base_url = self._guess_company_url(company_clean)
        logger.info("WebProvider: guessed base URL '%s' for company '%s'", base_url, company_clean)

        if not base_url:
            # If we can't guess a URL, we still return no evidence rather than hallucinating.
            return []

        # ------------------------------------------------------------------
        # 2) Crawl a small set of pages (home + careers)
        # ------------------------------------------------------------------
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=20.0, follow_redirects=True) as client:
            crawled_pages: Dict[str, str] = {}

            async def fetch_page(path: str) -> None:
                url = urljoin(base_url, path)
                try:
                    r = await client.get(url)
                    if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                        crawled_pages[url] = r.text
                        logger.info("WebProvider: fetched %s", url)
                except Exception:
                    logger.exception("WebProvider: error fetching %s", url)

            # Seed a small frontier: base, /careers, /jobs
            tasks = [
                fetch_page("/"),
                fetch_page("/careers"),
                fetch_page("/jobs"),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        # ------------------------------------------------------------------
        # 3) Extract raw text and discover GitHub link
        # ------------------------------------------------------------------
        all_text_chunks: List[str] = []
        github_urls: List[str] = []

        for url, html in crawled_pages.items():
            soup = BeautifulSoup(html, "html.parser")
            # text
            text = soup.get_text(separator="\n", strip=True)
            all_text_chunks.append(text)

            # discover GitHub links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "github.com" in href:
                    github_urls.append(href)

        combined_text = "\n".join(all_text_chunks).lower()

        # ------------------------------------------------------------------
        # 4) Optionally inspect GitHub profile (very light)
        # ------------------------------------------------------------------
        github_langs: List[str] = []
        if github_urls:
            github_root = self._normalize_github_url(github_urls[0])
            if github_root:
                github_langs = await self._fetch_github_languages(github_root)

        # ------------------------------------------------------------------
        # 5) Detect technologies from text + GitHub
        # ------------------------------------------------------------------
        (
            languages,
            ai_frameworks,
            frontend_frameworks,
            backend_frameworks,
            cloud_providers,
            databases,
            data_engineering,
            containers,
            orchestration,
            ci_cd,
            monitoring,
            security,
            cdn,
            api_technologies,
            mobile_technologies,
            web_servers,
            core_platforms,
            developer_platforms,
            products,
            innovation_focus,
        ) = self._detect_technologies(combined_text, github_langs)

        # ------------------------------------------------------------------
        # 6) Build structured profiles
        # ------------------------------------------------------------------
        technology_profile: Dict[str, List[str]] = {
            "languages": sorted(set(languages)),
            "ai_frameworks": sorted(set(ai_frameworks)),
            "cloud": sorted(set(cloud_providers)),
            "containers": sorted(set(containers)),
            "developer_platforms": sorted(set(developer_platforms)),
            "products": sorted(set(products)),
            "innovation_focus": sorted(set(innovation_focus)),
        }

        technology_intelligence: Dict[str, Any] = {
            "core_platforms": sorted(set(core_platforms)),
            "programming_languages": sorted(set(languages)),
            "frontend_frameworks": sorted(set(frontend_frameworks)),
            "backend_frameworks": sorted(set(backend_frameworks)),
            "ai_ml_frameworks": sorted(set(ai_frameworks)),
            "cloud_providers": sorted(set(cloud_providers)),
            "databases": sorted(set(databases)),
            "data_engineering": sorted(set(data_engineering)),
            "containerization": sorted(set(containers)),
            "orchestration": sorted(set(orchestration)),
            "ci_cd": sorted(set(ci_cd)),
            "monitoring": sorted(set(monitoring)),
            "security": sorted(set(security)),
            "cdn": sorted(set(cdn)),
            "api_technologies": sorted(set(api_technologies)),
            "mobile_technologies": sorted(set(mobile_technologies)),
            "web_servers": sorted(set(web_servers)),
        }

        # ------------------------------------------------------------------
        # 7) Emit ResearchEvidence
        # ------------------------------------------------------------------
        tech_profile_id = CitationManager.generate_id(
            "technology_profile",
            company_key,
            "technology_profile",
            "current",
        )
        evidence_list.append(
            ResearchEvidence(
                id=tech_profile_id,
                entity=company_key,
                attribute="technology_profile",
                value=technology_profile,
                source="web_technology_profile",
                source_type="mcp",
                confidence=0.7,  # heuristic, because detection is keyword-based
            )
        )

        tech_intel_id = CitationManager.generate_id(
            "technology_intelligence",
            company_key,
            "technology_intelligence",
            "current",
        )
        evidence_list.append(
            ResearchEvidence(
                id=tech_intel_id,
                entity=company_key,
                attribute="technology_intelligence",
                value=technology_intelligence,
                source="web_technology_profile",
                source_type="mcp",
                confidence=0.7,
            )
        )

        _write_json(
            f"web_evidence_{company_key.replace(' ', '_')[:40]}.json",
            [e.model_dump(mode="json") for e in evidence_list],
        )

        return evidence_list

    # ----------------------------------------------------------------------
    # URL guessing / normalization
    # ----------------------------------------------------------------------

    def _guess_company_url(self, company: str) -> Optional[str]:
        """
        Very naive URL guesser: in a real system this would be replaced by
        company metadata or a search/API call.

        For now, just try https://{company}.com if it looks like a single token.
        """
        token = company.lower().replace(" ", "")
        if not token:
            return None
        return f"https://{token}.com"

    def _normalize_github_url(self, url: str) -> Optional[str]:
        """
        Normalize to https://github.com/{org_or_user}
        """
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc:
            return None
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            return None
        return f"https://github.com/{parts[0]}"

    # ----------------------------------------------------------------------
    # GitHub inspection (very light)
    # ----------------------------------------------------------------------

    async def _fetch_github_languages(self, github_root: str) -> List[str]:
        """
        Fetch a list of languages from the GitHub profile page by scraping the
        'Most used languages' section on the user/org homepage.

        Note: this is heuristic and HTML-structure-dependent.
        """
        langs: List[str] = []
        try:
            async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=20.0, follow_redirects=True) as client:
                r = await client.get(github_root)
                if r.status_code != 200:
                    return []
                soup = BeautifulSoup(r.text, "html.parser")
                text = soup.get_text(separator="\n", strip=True).lower()
                # Cheap detection based on common languages
                candidates = [
                    "python",
                    "java",
                    "javascript",
                    "typescript",
                    "go",
                    "rust",
                    "c++",
                    "c#",
                    "php",
                    "ruby",
                ]
                for lang in candidates:
                    if lang in text:
                        langs.append(lang.capitalize() if lang != "c++" else "C++")
        except Exception:
            logger.exception("WebProvider: error fetching GitHub languages for %s", github_root)
        return list(set(langs))

    # ----------------------------------------------------------------------
    # Technology detection
    # ----------------------------------------------------------------------

    def _detect_technologies(
        self,
        text: str,
        github_langs: List[str],
    ) -> Tuple[
        List[str],  # languages
        List[str],  # ai_frameworks
        List[str],  # frontend_frameworks
        List[str],  # backend_frameworks
        List[str],  # cloud_providers
        List[str],  # databases
        List[str],  # data_engineering
        List[str],  # containers
        List[str],  # orchestration
        List[str],  # ci_cd
        List[str],  # monitoring
        List[str],  # security
        List[str],  # cdn
        List[str],  # api_technologies
        List[str],  # mobile_technologies
        List[str],  # web_servers
        List[str],  # core_platforms
        List[str],  # developer_platforms
        List[str],  # products
        List[str],  # innovation_focus
    ]:
        # Seed lists
        languages: List[str] = []
        ai_frameworks: List[str] = []
        frontend_frameworks: List[str] = []
        backend_frameworks: List[str] = []
        cloud_providers: List[str] = []
        databases: List[str] = []
        data_engineering: List[str] = []
        containers: List[str] = []
        orchestration: List[str] = []
        ci_cd: List[str] = []
        monitoring: List[str] = []
        security: List[str] = []
        cdn: List[str] = []
        api_technologies: List[str] = []
        mobile_technologies: List[str] = []
        web_servers: List[str] = []
        core_platforms: List[str] = []
        developer_platforms: List[str] = []
        products: List[str] = []
        innovation_focus: List[str] = []

        # Languages (from text + GitHub)
        lang_map = {
            "c++": "C++",
            "cuda": "CUDA",
            "python": "Python",
            "rust": "Rust",
            "java": "Java",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "go": "Go",
            "c#": "C#",
            "php": "PHP",
        }
        for raw, norm in lang_map.items():
            if raw in text:
                languages.append(norm)
        for gl in github_langs:
            if gl not in languages:
                languages.append(gl)

        # AI frameworks
        ai_map = {
            "tensorrt": "TensorRT",
            "cudnn": "cuDNN",
            "triton": "Triton",
            "nemo": "NeMo",
            "pytorch": "PyTorch",
            "tensorflow": "TensorFlow",
            "scikit-learn": "scikit-learn",
            "sklearn": "scikit-learn",
            "xgboost": "XGBoost",
            "nim": "NIM",
        }
        for raw, norm in ai_map.items():
            if raw in text:
                ai_frameworks.append(norm)

        # Cloud providers
        cloud_map = {
            "aws": "AWS",
            "amazon web services": "AWS",
            "azure": "Azure",
            "google cloud": "Google Cloud",
            "gcp": "Google Cloud",
            "oci": "OCI",
            "oracle cloud": "OCI",
        }
        for raw, norm in cloud_map.items():
            if raw in text:
                cloud_providers.append(norm)

        # Containers / orchestration
        if "docker" in text:
            containers.append("Docker")
        if "kubernetes" in text or "k8s" in text:
            containers.append("Kubernetes")
            orchestration.append("Kubernetes")

        # Frontend frameworks
        if "react" in text:
            frontend_frameworks.append("React")
        if "vue" in text:
            frontend_frameworks.append("Vue")
        if "angular" in text:
            frontend_frameworks.append("Angular")
        if "next.js" in text or "nextjs" in text:
            frontend_frameworks.append("Next.js")

        # Backend frameworks
        if "django" in text:
            backend_frameworks.append("Django")
        if "flask" in text:
            backend_frameworks.append("Flask")
        if "fastapi" in text:
            backend_frameworks.append("FastAPI")
        if "spring boot" in text:
            backend_frameworks.append("Spring Boot")
        if "node.js" in text or "nodejs" in text:
            backend_frameworks.append("Node.js")

        # Databases
        db_map = {
            "mysql": "MySQL",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "oracle": "Oracle",
            "sql server": "SQL Server",
            "mongodb": "MongoDB",
            "redis": "Redis",
        }
        for raw, norm in db_map.items():
            if raw in text:
                databases.append(norm)

        # Data engineering
        if "kafka" in text:
            data_engineering.append("Kafka")
        if "spark" in text:
            data_engineering.append("Spark")
        if "airflow" in text:
            data_engineering.append("Airflow")

        # CI/CD
        if "github actions" in text:
            ci_cd.append("GitHub Actions")
        if "jenkins" in text:
            ci_cd.append("Jenkins")
        if "gitlab ci" in text or "gitlab-ci" in text:
            ci_cd.append("GitLab CI")
        if "circleci" in text:
            ci_cd.append("CircleCI")

        # Monitoring
        if "prometheus" in text:
            monitoring.append("Prometheus")
        if "grafana" in text:
            monitoring.append("Grafana")
        if "datadog" in text:
            monitoring.append("Datadog")

        # Security
        if "vault" in text:
            security.append("Vault")
        if "snyk" in text:
            security.append("Snyk")

        # CDN
        if "cloudflare" in text:
            cdn.append("Cloudflare")
        if "akamai" in text:
            cdn.append("Akamai")

        # API technologies
        if "rest api" in text or "restful api" in text:
            api_technologies.append("REST")
        if "graphql" in text:
            api_technologies.append("GraphQL")
        if "grpc" in text:
            api_technologies.append("gRPC")

        # Mobile
        if "android" in text:
            mobile_technologies.append("Android")
        if "ios" in text:
            mobile_technologies.append("iOS")
        if "flutter" in text:
            mobile_technologies.append("Flutter")
        if "react native" in text:
            mobile_technologies.append("React Native")

        # Web servers
        if "nginx" in text:
            web_servers.append("NGINX")
        if "apache httpd" in text or "apache http server" in text:
            web_servers.append("Apache HTTPD")
        if "envoy" in text:
            web_servers.append("Envoy")

        # Core platforms / developer platforms / products / innovation focus
        if "nvidia" in text and "gpu" in text:
            core_platforms.append("NVIDIA GPU Platform")
        if "nvidia ai enterprise" in text:
            core_platforms.append("NVIDIA AI Enterprise")
        if "nvidia developer" in text:
            developer_platforms.append("NVIDIA Developer")
        if "ngc" in text:
            developer_platforms.append("NGC")
        if "github" in text:
            developer_platforms.append("GitHub")

        # Products (based on your example)
        product_map = {
            "blackwell": "Blackwell",
            "h100": "H100",
            "dgx": "DGX",
            "grace": "Grace",
            "jetson": "Jetson",
        }
        for raw, norm in product_map.items():
            if raw in text:
                products.append(norm)

        # Innovation focus
        if "generative ai" in text or "gen ai" in text:
            innovation_focus.append("Generative AI")
        if "inference" in text:
            innovation_focus.append("Inference")
        if "digital twin" in text:
            innovation_focus.append("Digital Twins")
        if "robotics" in text:
            innovation_focus.append("Robotics")
        if "ai factory" in text or "ai factories" in text:
            innovation_focus.append("AI Factories")

        return (
            languages,
            ai_frameworks,
            frontend_frameworks,
            backend_frameworks,
            cloud_providers,
            databases,
            data_engineering,
            containers,
            orchestration,
            ci_cd,
            monitoring,
            security,
            cdn,
            api_technologies,
            mobile_technologies,
            web_servers,
            core_platforms,
            developer_platforms,
            products,
            innovation_focus,
        )
