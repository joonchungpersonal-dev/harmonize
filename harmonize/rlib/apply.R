#!/usr/bin/env Rscript
# Deterministic harmonization engine (R side).
# Reads a fully-resolved crosswalk config (JSON) and emits pooled.csv +
# manifest.json. Makes NO judgments: every rule comes from the config.
suppressMessages({
  library(jsonlite)
  library(haven)
})

args <- commandArgs(trailingOnly = TRUE)
cfg <- fromJSON(args[1], simplifyVector = FALSE)
out_dir <- args[2]

read_any <- function(path) {
  ext <- tolower(tools::file_ext(path))
  if (ext == "rds") {
    return(as.data.frame(readRDS(path)))
  }
  if (ext %in% c("sav")) {
    return(as.data.frame(haven::read_sav(path)))
  }
  if (ext %in% c("dta")) {
    return(as.data.frame(haven::read_dta(path)))
  }
  if (ext %in% c("xpt")) {
    return(as.data.frame(haven::read_xpt(path)))
  }
  as.data.frame(read.csv(path, stringsAsFactors = FALSE))
}

key <- unlist(cfg$key)
id_key <- key[length(key)] # last key element is the source/cycle id (e.g. "cycle")
person_keys <- setdiff(key, id_key)
items <- cfg$items
item_names <- vapply(items, function(x) x$name, character(1))

rows_in_total <- 0L
residual_sentinels <- 0L
frames <- list()

for (src in cfg$sources) {
  d <- read_any(src$path)
  rows_in_total <- rows_in_total + nrow(d)
  block <- data.frame(matrix(nrow = nrow(d), ncol = 0))
  # person-level keys carried straight through
  for (pk in person_keys) block[[pk]] <- d[[pk]]
  block[[id_key]] <- src$id
  for (it in items) {
    raw <- d[[it$source_vars[[src$id]]]]
    raw <- as.numeric(raw)
    sent <- cfg$sentinels$by_item[[it$name]]
    if (is.null(sent)) sent <- cfg$sentinels$default
    sent <- unlist(sent)
    if (length(sent)) {
      residual_sentinels <- residual_sentinels + sum(raw %in% sent, na.rm = TRUE)
      raw[raw %in% sent] <- NA # sentinel -> NA BEFORE any numeric op
    }
    block[[it$name]] <- raw
  }
  frames[[length(frames) + 1]] <- block
}

pooled <- do.call(rbind, frames)

# Composite with proration: score only if >= min_items_present present.
mip <- cfg$composite$min_items_present
rule <- cfg$composite$rule
M <- as.matrix(pooled[, item_names, drop = FALSE])
present <- rowSums(!is.na(M))
agg <- if (rule == "mean") rowMeans(M, na.rm = TRUE) else rowSums(M, na.rm = TRUE)
agg[present < mip] <- NA
pooled[[cfg$composite$name]] <- agg

# residual_sentinels recomputed on the OUTPUT item columns (must be 0 post-map).
residual_out <- sum(vapply(item_names, function(nm) {
  sent <- cfg$sentinels$by_item[[nm]]
  if (is.null(sent)) sent <- cfg$sentinels$default
  sent <- unlist(sent)
  if (!length(sent)) {
    return(0L)
  }
  sum(pooled[[nm]] %in% sent, na.rm = TRUE)
}, integer(1)))

key_duplicates <- sum(duplicated(pooled[, key, drop = FALSE]))

manifest <- list(
  rows_in_total = rows_in_total,
  rows_out = nrow(pooled),
  key_duplicates = as.integer(key_duplicates),
  residual_sentinels = as.integer(residual_out),
  composite_missing = as.integer(sum(is.na(pooled[[cfg$composite$name]]))),
  composite_mean = round(mean(pooled[[cfg$composite$name]], na.rm = TRUE), 4)
)

write.csv(pooled, file.path(out_dir, "pooled.csv"), row.names = FALSE)
write(toJSON(manifest, auto_unbox = TRUE, pretty = TRUE),
  file = file.path(out_dir, "manifest.json")
)
