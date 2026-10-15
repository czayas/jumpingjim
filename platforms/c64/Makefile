# Jumping Jim - Commodore 64
# Requires: python3 + Pillow, acme, c1541 (VICE) for the .d64
ASSETS  := ../../assets
BUILD   := build
GEN     := $(BUILD)/tables.a
PRG     := $(BUILD)/jumpingjim.prg
D64     := $(BUILD)/jumpingjim.d64

all: $(PRG) $(D64)

$(GEN): $(ASSETS)/jumpingjim.json $(wildcard $(ASSETS)/backgrounds/*.png) tools/convert_c64.py ../../tools/lzpack.py
	python3 tools/convert_c64.py $(ASSETS) $(BUILD)

# the RIP intro (lib/rip-intro: the logo converted for its module)
RIP := ../../lib/rip-intro
$(BUILD)/rip_logo.bin: $(RIP)/assets/rip_logo.png $(RIP)/tools/convertir.py
	mkdir -p $(BUILD)
	python3 $(RIP)/tools/convertir.py $< $@ --modo multi --celdas 17x24 --col 11 --fila 0

# the .lbl file (addresses of the labels, VICE format) is used by the tests
$(PRG): src/main.a $(RIP)/c64/rip_intro.a $(BUILD)/rip_logo.bin $(GEN)
	cd src && acme -f cbm --vicelabels ../$(BUILD)/jumpingjim.lbl -o ../$(PRG) main.a

# test build: scripted input (jump + walk right), used for automated screenshots
test: $(GEN) $(BUILD)/rip_logo.bin
	cd src && acme -f cbm -DTEST=5 -o ../$(BUILD)/test.prg main.a

# autopilot demo used for the promo video (title for 5 s, then plays from level 2)
promo: $(GEN) $(BUILD)/rip_logo.bin
	cd src && acme -f cbm -DTEST=7 -DPROMO=1 -DSTARTLEVEL=2 -DSTARTBCD=2 -o ../$(BUILD)/promo.prg main.a

$(D64): $(PRG)
	rm -f $@
	c1541 -format "jumping jim,jj" d64 $@ -write $(PRG) "jumping jim" >/dev/null

run: $(PRG)
	x64sc -autostart $(PRG)

# automated tests in headless VICE (see ../../docs/testing.md)
#   make check      play the scenarios and compare with tests/ref-pal (real
#                   timing) and tests/ref-pal-logic (game logic only)
#   make reference  record both references again (after an intended change)
#   make frametime  CPU time used per frame, PAL and NTSC
check: $(PRG)
	python3 tests/run_tests.py check tests/ref-pal
	python3 tests/run_tests.py check tests/ref-pal-logic

reference: $(PRG)
	rm -rf tests/ref-pal tests/ref-pal-logic
	python3 tests/run_tests.py record tests/ref-pal
	python3 tests/run_tests.py record tests/ref-pal-logic --clock logic
	rm -rf tests/ref-pal/shots tests/ref-pal-logic/shots

frametime: $(PRG)
	python3 tests/frame_time.py

clean:
	rm -rf $(BUILD)

# release packaging, used by tools/release.sh:  make dist VERSION=v1.0.0
VERSION ?= dev
DIST    := ../../dist
dist: $(PRG) $(D64)
	mkdir -p $(DIST)/c64
	cp $(D64) $(DIST)/jumpingjim-c64-$(VERSION).d64
	cp $(PRG) $(DIST)/jumpingjim-c64-$(VERSION).prg
	cp $(D64) $(PRG) $(DIST)/c64/
	cp ../../LICENSE ../../NOTICE.md $(DIST)/c64/
	printf 'Jumping Jim - Commodore 64 %s\n\nLOAD"*",8,1 and RUN (or open the .d64 in VICE).\nKeys: O/Z left, P/X right, Q/SPACE jump. Joystick in port 2 or 1.\nF1 on the title screen: extra effects (backgrounds, screen shake) on/off.\nRuns on PAL, NTSC and PAL-N (Drean) machines.\n\nOriginal game by roman126 - https://roman126.itch.io/jumping-jim-zx-spectrum-next\nC64 port by Carlos Zayas (AI-assisted) - https://github.com/czayas/jumpingjim\n' $(VERSION) > $(DIST)/c64/README.txt
	cd $(DIST)/c64 && rm -f ../jumpingjim-c64-$(VERSION).zip && zip -q -r ../jumpingjim-c64-$(VERSION).zip .
	rm -rf $(DIST)/c64

.PHONY: all test promo run check reference frametime clean dist
