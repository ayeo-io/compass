# Run by scripts/lib/python-check.sh: print python3's version, and exit 1 when it
# is older than 3.10. Kept to syntax any python3 reads, so an old one reports.
# Standard input is closed.
import sys; v = sys.version_info; print("%d.%d.%d" % tuple(v[:3])); sys.exit(0 if v >= (3, 10) else 1)
