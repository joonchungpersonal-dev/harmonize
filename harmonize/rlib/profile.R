#!/usr/bin/env Rscript
# Deterministic per-variable profiling. Emits JSON to stdout.
suppressMessages({
  library(jsonlite)
  library(haven)
})

args <- commandArgs(trailingOnly = TRUE)

read_any <- function(path) {
  ext <- tolower(tools::file_ext(path))
  if (ext == "rds") {
    return(as.data.frame(readRDS(path)))
  }
  if (ext == "sav") {
    return(as.data.frame(haven::read_sav(path)))
  }
  if (ext == "dta") {
    return(as.data.frame(haven::read_dta(path)))
  }
  if (ext == "xpt") {
    return(as.data.frame(haven::read_xpt(path)))
  }
  as.data.frame(read.csv(path, stringsAsFactors = FALSE))
}

out <- list()
for (path in args) {
  d <- read_any(path)
  vars <- lapply(names(d), function(nm) {
    v <- d[[nm]]
    num <- suppressWarnings(as.numeric(v))
    tab <- sort(table(num), decreasing = TRUE)
    list(
      name = nm,
      n = sum(!is.na(v)),
      pct_miss = round(mean(is.na(v)) * 100, 1),
      distinct = length(unique(na.omit(v))),
      top_values = head(as.numeric(names(tab)), 6)
    )
  })
  out[[basename(path)]] <- list(rows = nrow(d), variables = vars)
}
cat(toJSON(out, auto_unbox = TRUE, pretty = TRUE))
