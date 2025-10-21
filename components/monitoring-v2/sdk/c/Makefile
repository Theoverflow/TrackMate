# Makefile for C SDK

CC = gcc
CFLAGS = -Wall -Wextra -O2 -pthread
TARGET = example
OBJS = monitoring_sdk.o example.o

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJS)

monitoring_sdk.o: monitoring_sdk.c monitoring_sdk.h
	$(CC) $(CFLAGS) -c monitoring_sdk.c

example.o: example.c monitoring_sdk.h
	$(CC) $(CFLAGS) -c example.c

clean:
	rm -f $(TARGET) $(OBJS)

.PHONY: all clean

