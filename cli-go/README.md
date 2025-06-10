# Go CLI for LLM Backend

This folder contains a cross-platform command line client written in Go. The CLI can be built as a single executable for Windows, Linux and macOS.

## Features

- Interactive colour-coded chat sessions
- Upload documents to the API
- List, read, write and delete files in the VM

## Building

Install Go 1.20 or later and run:

```bash
cd cli-go
go build -o llmcli
```

For other platforms pass `GOOS` and `GOARCH` environment variables:

```bash
GOOS=windows GOARCH=amd64 go build -o llmcli.exe
```

## Usage

```
./llmcli --user yourname --server http://localhost:8000 chat
```

Use `--help` on any subcommand for details.

