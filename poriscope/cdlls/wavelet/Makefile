# wavelet DLL cross-platform Makefile

# Output and object settings
E      = .dll
O      = o
ODIR   = build/obj
OUT    = dist/wavelet$(E)
SRC    = src
INC    = lib
INCDIR = -I$(INC)
DEPS   = $(wildcard $(INC)/*.h)

# C compiler
CC     = x86_64-w64-mingw32-gcc
CFLAGS = -O3 -D_GNU_SOURCE -fPIC -Wall
LIBS   = -lm

# Source files
_SRCS  = wavelet_filter wdenoise ebayesthresh wdenmath wavefilt wavefunc \
         wavelib wtmath cwt cwtmath hsfft real conv utils
OBJS   = $(patsubst %,$(ODIR)/%.$(O),$(_SRCS))

# Default target
all: $(OUT)

# Compile .c to .o
$(ODIR)/%.$(O): $(SRC)/%.c $(DEPS)
	@mkdir -p $(ODIR)
	$(CC) -c -o $@ $< $(CFLAGS) $(INCDIR)

# Link objects into DLL
$(OUT): $(OBJS)
	@mkdir -p dist
	$(CC) -shared -o $@ $^ $(CFLAGS) $(INCDIR) $(LIBS)

# Clean target (cross-platform)
clean:
	rm -f $(OUT) $(ODIR)/*.$(O)
