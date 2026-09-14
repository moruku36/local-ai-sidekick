"""Secret scanning utility for Sidekick pre-commit Diff Guard."""
import re
from pathlib import Path
from typing import List, Tuple

SECRET_PATTERNS = [
    (r"gh[opusr]_[A-Za-z0-9_]{20,}", "GitHub Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9\/+=]{40}['\"]?", "AWS Secret Key"),
    (r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer Token"),
    (r"(?i)(password|secret|api_key|apikey|private_key)\s*[:=]\s*['\"][^'\"]{6,}['\"]", "Generic Secret Assignment"),
    (r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key Header"),
    (r"-----BEGIN CERTIFICATE-----", "Certificate Header"),
]

class SecretScanner:
    @classmethod
    def scan_text(cls, text: str, filename: str = "") -> List[Tuple[int, str, str]]:
        """Scans string for secret patterns. Returns [(line_no, rule_name, filename)]."""
        findings = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern, rule_name in SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append((line_no, rule_name, filename))
                    break
        return findings

    @classmethod
    def scan_file(cls, file_path: Path) -> List[Tuple[int, str, str]]:
        """Scans a file for potential secrets."""
        if not file_path.exists() or not file_path.is_file():
            return []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return cls.scan_text(content, str(file_path))
        except Exception:
            return []
