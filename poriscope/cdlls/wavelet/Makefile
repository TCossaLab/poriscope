# wavelet DLL cross-platform Makefile

ifeq ($(CROSS),true)
    CC     = x86_64-w64-mingw32-gcc
    E      = .dll
    RM     = rm -f
    MKDIR  = mkdir -p
    RMDIR  = rm -rf
    SEP    = /
else
    ifeq ($(OS),Windows_NT)
        CC     = x86_64-w64-mingw32-gcc
        E      = .dll
        RM     = del /F /Q
        MKDIR  = if not exist
        RMDIR  = rmdir /S /Q
        SEP    = \\
    else
        CC     = gcc
        E      = .so
        RM     = rm -f
        MKDIR  = mkdir -p
        RMDIR  = rm -rf
        SEP    = /
    endif
endif

# Output and object settings
O      = o
ODIR   = build/obj
OUT    = dist$(SEP)wavelet$(E)
SRC    = src
INC    = lib
INCDIR = -I$(INC)
DEPS   = $(wildcard $(INC)/*.h)

# C compiler
CFLAGS = -O3 -D_GNU_SOURCE -fPIC -Wall
LIBS   = -lm

# Source files

_SRCS  = wavelet_filter wdenoise ebayesthresh wdenmath wavefilt wavefunc \
         wavelib wtmath cwt cwtmath hsfft real conv utils
OBJS   = $(patsubst %,$(ODIR)$(SEP)%.$(O),$(_SRCS))

.PHONY: all clean

# Default target
all: $(OUT)

# Compile .c to .o
$(ODIR)$(SEP)%.$(O): $(SRC)/%.c $(DEPS)
	@$(MKDIR) $(ODIR)
	$(CC) -c -o $@ $< $(CFLAGS) $(INCDIR)

# Link objects into DLL
$(OUT): $(OBJS)
	@$(MKDIR) dist
	$(CC) -shared -o $@ $^ $(CFLAGS) $(INCDIR) $(LIBS)


# Clean target (cross-platform)
clean:
	-$(RM) $(OUT)
	-$(RM) $(ODIR)$(SEP)*.$(O)
