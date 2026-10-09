# Jumping Jim - multi-platform build
.PHONY: all assets c64 clean

all: c64

assets:
	python3 tools/extract.py original/JumpingJim_v4.nex assets

c64:
	$(MAKE) -C platforms/c64

clean:
	$(MAKE) -C platforms/c64 clean
