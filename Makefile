# Jumping Jim - multi-platform build
.PHONY: all assets c64 clean release

all: c64

assets:
	python3 tools/extract.py original/JumpingJim_v4.nex assets

c64:
	$(MAKE) -C platforms/c64

clean:
	$(MAKE) -C platforms/c64 clean

# publish a GitHub release:  make release VERSION=v1.0.0
release:
	tools/release.sh $(VERSION)
