"""Design Agent module.

Implements the DesignAgent that produces comprehensive architecture designs
from research findings and requirements profiles.

Responsibilities:
- Generate complete ArchitectureReport with services, networking, VPC, security, costs
- Perform Well-Architected Framework review
- Respect budget constraints with documented trade-offs
- Include IaC skeleton when iac_preference is specified
- Omit VPC for fully serverless architectures
"""
