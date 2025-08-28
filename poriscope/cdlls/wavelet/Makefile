# Auto-detect platform and configure compiler, file extension,
# path separators, and removal commands depending on OS.
ifeq ($(OS),Windows_NT)
    RM       = del /Q
    SEP      = \\
    E        = .dll
    CC       = x86_64-w64-mingw32-gcc
    RM_NULL  = nul
    DETECTED_OS = Windows
    SHELLTYPE = windows
else
    UNAME_S  := $(shell uname -s)
    RM       = rm -f
    SEP      = /
    ifeq ($(UNAME_S),Darwin)
        E    = .dylib
        CC   = clang
    else
        E    = .so
        CC   = gcc
    endif
    RM_NULL  = /dev/null
    DETECTED_OS = $(UNAME_S)
    SHELLTYPE = posix
endif

# A portable "make directory" helper:
# - On Windows/cmd: "if not exist DIR mkdir DIR"
# - On POSIX shells: "mkdir -p DIR"
define make_dir
$(if $(filter windows,$(SHELLTYPE)),\
	@if not exist "$(1)" mkdir "$(1)" 2>$(RM_NULL),\
	@mkdir -p "$(1)" 2>$(RM_NULL))
endef

# Directories, flags, and libraries
O             = o
ODIR          = build$(SEP)obj
SRC           = src
INC           = lib
INCDIR        = -I$(INC)
CFLAGS_COMMON = -O3 -fPIC -Wall
CFLAGS        = $(CFLAGS_COMMON)
LIBS          = -lm

# Source files and corresponding object files
_SRCS  = wavelet_filter wdenoise ebayesthresh wdenmath wavefilt wavefunc \
         wavelib wtmath cwt cwtmath hsfft real conv utils
OBJS   = $(patsubst %,$(ODIR)$(SEP)%.$(O),$(_SRCS))

# Output shared library name (default target)
OUT    = dist$(SEP)wavelet$(E)

# Phony targets
.PHONY: all clean dll so dylib build

# Build all variants
all: dll so dylib

# Windows DLL
dll: E = .dll
dll: CC = x86_64-w64-mingw32-gcc
dll: OUT = dist$(SEP)wavelet.dll
dll: CFLAGS = $(CFLAGS_COMMON)
dll: build

# Linux SO
so: E = .so
so: CC = gcc
so: OUT = dist$(SEP)wavelet.so
so: CFLAGS = $(CFLAGS_COMMON)
so: build

# macOS DYLIB (when built on Linux, this is a clang-built .dylib for naming/tests)
dylib: E = .dylib
dylib: CC = clang
dylib: OUT = dist$(SEP)wavelet.dylib
# Only the dylib target needs the feature macros due to fopen64/fseeko64/ftello64
dylib: CFLAGS = $(CFLAGS_COMMON) -std=c99 -D_LARGEFILE64_SOURCE -D_FILE_OFFSET_BITS=64 -D_GNU_SOURCE
dylib: build

# General build target: cleans and builds the library
build: clean $(OUT)

# Compile object files
$(ODIR)$(SEP)%.$(O): $(SRC)/%.c $(wildcard $(INC)/*.h)
	$(call make_dir,$(ODIR))
	$(CC) -c -o $@ $< $(CFLAGS) $(INCDIR)

# Link shared library
$(OUT): $(OBJS)
	$(call make_dir,dist)
	$(CC) -shared -o $@ $^ $(CFLAGS) $(INCDIR) $(LIBS)

# Clean artifacts
clean:
	-$(RM) dist$(SEP)*.dll dist$(SEP)*.so dist$(SEP)*.dylib 2>$(RM_NULL)
	-$(RM) $(ODIR)$(SEP)*.$(O) 2>$(RM_NULL)
