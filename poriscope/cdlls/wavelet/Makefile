# ============================
# Cross-platform basics
# ============================
ifeq ($(OS),Windows_NT)
    SEP      = \\
    RM       = del /Q
    RM_NULL  = nul
else
    SEP      = /
    RM       = rm -f
    RM_NULL  = /dev/null
endif

# A tiny portable mkdir helper (macro used inside recipes)
define MKDIR
@if not exist "$(1)" mkdir "$(1)" 2>$(RM_NULL)
endef
ifeq ($(SEP),/)
  define MKDIR
  @mkdir -p "$(1)" 2>$(RM_NULL)
  endef
endif

# ============================
# Common config
# ============================
SRC           = src
INC           = lib
INCDIR        = -I$(INC)
CFLAGS_COMMON = -O3 -fPIC -Wall
LIBS          = -lm

_SRCS = wavelet_filter wdenoise ebayesthresh wdenmath wavefilt wavefunc \
        wavelib wtmath cwt cwtmath hsfft real conv utils

# Per-mode defaults; overridden below based on MODE
ODIR  ?= build$(SEP)obj_default
OUT   ?= dist$(SEP)wavelet.so
CC    ?= gcc
CFLAGS?= $(CFLAGS_COMMON)

# Compute object list AFTER ODIR is known (inside sub-make)
OBJS  = $(patsubst %,$(ODIR)$(SEP)%.o,$(_SRCS))

.PHONY: all clean so dll dylib all_one

# Top-level convenience targets: spawn sub-make with MODE
all: so dll dylib

so:
	$(MAKE) MODE=so  all_one

dll:
	$(MAKE) MODE=dll all_one

dylib:
	$(MAKE) MODE=dylib all_one

# ============================
# Mode selection (evaluated in sub-make)
# ============================
ifeq ($(MODE),so)
    CC     = gcc
    OUT    = dist$(SEP)wavelet.so
    ODIR   = build$(SEP)obj_gcc
    CFLAGS = $(CFLAGS_COMMON)
endif

ifeq ($(MODE),dll)
    CC     = x86_64-w64-mingw32-gcc
    OUT    = dist$(SEP)wavelet.dll
    ODIR   = build$(SEP)obj_mingw
    CFLAGS = $(CFLAGS_COMMON)
endif

ifeq ($(MODE),dylib)
    CC     = clang
    OUT    = dist$(SEP)wavelet.dylib
    ODIR   = build$(SEP)obj_clang
    # Only clang/dylib needs the feature macros for *64 file APIs
    CFLAGS = $(CFLAGS_COMMON) -std=c99 -D_LARGEFILE64_SOURCE -D_FILE_OFFSET_BITS=64 -D_GNU_SOURCE
endif

# ============================
# One-mode build
# ============================
all_one: $(OUT)

$(OUT): $(OBJS)
	$(call MKDIR,dist)
	$(CC) -shared -o $@ $^ $(CFLAGS) $(INCDIR) $(LIBS)

# Compile rule (uses mode-specific ODIR/CC/CFLAGS)
$(ODIR)$(SEP)%.o: $(SRC)/%.c $(wildcard $(INC)/*.h)
	$(call MKDIR,$(ODIR))
	$(CC) -c -o $@ $< $(CFLAGS) $(INCDIR)

# ============================
# Clean
# ============================
clean:
	-$(RM) dist$(SEP)*.so dist$(SEP)*.dll dist$(SEP)*.dylib 2>$(RM_NULL)
	-$(RM) build$(SEP)obj_gcc$(SEP)*.o    2>$(RM_NULL)
	-$(RM) build$(SEP)obj_mingw$(SEP)*.o  2>$(RM_NULL)
	-$(RM) build$(SEP)obj_clang$(SEP)*.o  2>$(RM_NULL)
