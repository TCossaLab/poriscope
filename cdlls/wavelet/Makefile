O = obj
E = .dll
CC = x86_64-w64-mingw32-gcc
OUT_DIST = dist/wavelet$(E)
CFLAGS = -D_GNU_SOURCE -O3 -shared -fPIC
INCDIR = lib/
DEPS = lib/*.h
ODIR = build/obj
_OBJ = wavelet_filter.$(O) wdenoise.$(O) ebayesthresh.$(O) wdenmath.$(O) wavefilt.$(O) wavefunc.$(O) wavelib.$(O) wtmath.$(O) cwt.$(O) cwtmath.$(O) hsfft.$(O) real.$(O) conv.$(O) utils.$(O)
OBJ = $(patsubst %,$(ODIR)/%,$(_OBJ))

LIBS = -lm

$(ODIR)/%.$(O): src/%.c $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS) -I$(INCDIR) $(LIBS)

$(OUT_DIST): $(OBJ)
	$(CC) -shared -o $@ $^ $(CFLAGS) -I$(INCDIR) $(LIBS)

.PHONY: all clean

all: $(OUT_DIST)

clean:
	del /F /Q $(subst /,\,$(OUT_DIST)) $(subst /,\,$(OUT_SRC)) $(subst /,\,$(ODIR))\*.$(O)
