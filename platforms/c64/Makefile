# Jumping Jim - Commodore 64
# Requires: python3 (+Pillow optional), acme, c1541 (VICE) for the .d64
ASSETS  := ../../assets
BUILD   := build
GEN     := $(BUILD)/tables.a
PRG     := $(BUILD)/jumpingjim.prg
D64     := $(BUILD)/jumpingjim.d64

all: $(PRG) $(D64)

$(GEN): $(ASSETS)/jumpingjim.json tools/convert_c64.py
	python3 tools/convert_c64.py $(ASSETS) $(BUILD)

$(PRG): src/main.a $(GEN)
	cd src && acme -f cbm -o ../$(PRG) main.a

# test build: scripted input (jump + walk right), used for automated screenshots
test: $(GEN)
	cd src && acme -f cbm -DTEST=5 -o ../$(BUILD)/test.prg main.a

# autopilot demo used for the promo video (title for 5 s, then plays from level 2)
promo: $(GEN)
	cd src && acme -f cbm -DTEST=7 -DPROMO=1 -DSTARTLEVEL=2 -DSTARTBCD=2 -o ../$(BUILD)/promo.prg main.a

$(D64): $(PRG)
	rm -f $@
	c1541 -format "jumping jim,jj" d64 $@ -write $(PRG) "jumping jim" >/dev/null

run: $(PRG)
	x64sc -autostart $(PRG)

clean:
	rm -rf $(BUILD)

.PHONY: all test promo run clean
