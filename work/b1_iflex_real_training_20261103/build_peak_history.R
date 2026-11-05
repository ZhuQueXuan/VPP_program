# Extract the two same-clock peak-history features from official meter readings.
args <- commandArgs(trailingOnly = TRUE)
if (.Platform$OS.type == "windows") invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
root <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
output <- file.path(root, "work/b1_iflex_real_training_20261103")
prepared_path <- file.path(root, "work/b1_real_response_data_20261103/prepared_P_events.csv")
archive_directory <- "\u632a\u5a01_iFlex_\u52a8\u6001\u7535\u4ef7\u8bd5\u9a8c"
archive_path <- file.path(root, "data/public_datasets", archive_directory, "iFlex_dataset.RData")
features_path <- file.path(output, "features_peak_history.csv")
verification_path <- file.path(output, "peak_history_verification.json")
stopifnot(!file.exists(features_path), !file.exists(verification_path))

header <- names(read.csv(prepared_path, nrows = 0L, check.names = FALSE))
metadata <- c("ID", "Group", "Date", "split", "notice_utc")
stopifnot(all(metadata %in% header))
classes <- ifelse(header %in% metadata, "character", "NULL")
events <- read.csv(prepared_path, colClasses = classes, check.names = FALSE)
stopifnot(identical(names(events), metadata), nrow(events) == 14213L,
          !anyDuplicated(events[c("ID", "Date", "Group")]))
utc_format <- "%Y-%m-%dT%H:%M:%SZ"
notice <- as.numeric(as.POSIXct(events$notice_utc, format = utc_format, tz = "UTC"))
stopifnot(all(is.finite(notice)))
lookback <- 168 * 3600

archive_md5 <- unname(tools::md5sum(archive_path))
stopifnot(archive_md5 == "7547c0931b0cda997609d9e7df70fdd2")
archive <- new.env(parent = emptyenv())
load(archive_path, envir = archive)
raw <- archive$data_hourly
ids <- unique(events$ID)
peak_source <- which(raw$Participation_Phase == "Phase_2" &
                     raw$Hour %in% c(17L, 18L) & raw$ID %in% ids)
source_by_id <- split(peak_source, as.character(raw$ID[peak_source]))
events_by_id <- split(seq_len(nrow(events)), events$ID)
stopifnot(all(ids %in% names(source_by_id)))

features <- events
features$mean_peak_history_kwh <- rep(NA_real_, nrow(events))
features$most_recent_complete_peak_kwh <- rep(NA_real_, nrow(events))
features$pairs_count <- integer(nrow(events))
features$latest_available_utc <- rep(NA_character_, nrow(events))
features$latest_source_row17 <- rep(NA_integer_, nrow(events))
features$latest_source_row18 <- rep(NA_integer_, nrow(events))
features$history_peak_source_pairs <- rep("", nrow(events))
format_utc <- function(seconds) {
  format(as.POSIXct(seconds, origin = "1970-01-01", tz = "UTC"), utc_format, tz = "UTC")
}
pair_string <- function(first, second) paste(paste(first, second, sep = ":"), collapse = ";")
all_pairs <- 0L
min_cutoff_margin <- Inf
min_window_start_margin <- Inf

for (id in ids) {
  rows <- source_by_id[[id]]
  first <- rows[raw$Hour[rows] %in% 17L]
  second <- rows[raw$Hour[rows] %in% 18L]
  first_day <- as.character(raw$Date[first])
  second_day <- as.character(raw$Date[second])
  unique_first <- !(duplicated(first_day) | duplicated(first_day, fromLast = TRUE))
  unique_second <- !(duplicated(second_day) | duplicated(second_day, fromLast = TRUE))
  match_second <- match(first_day, second_day)
  have_both <- which(!is.na(first_day) & unique_first & !is.na(match_second) & unique_second[match_second])
  first <- first[have_both]
  second <- second[match_second[have_both]]
  start <- as.numeric(raw$From[first])
  last_hour_start <- as.numeric(raw$From[second])
  complete <- which(is.finite(start) & is.finite(last_hour_start) & last_hour_start - start == 3600)
  first <- first[complete]
  second <- second[complete]
  start <- start[complete]
  end <- last_hour_start[complete] + 3600
  for (j in events_by_id[[id]]) {
    use <- which(start >= notice[j] - lookback & end <= notice[j])
    if (!length(use)) next
    use <- use[order(end[use])]
    # Only access Demand_kWh after both timestamps have passed the as-of filter.
    stopifnot(all(start[use] >= notice[j] - lookback), all(end[use] <= notice[j]),
              all(as.character(raw$Date[first[use]]) < events$Date[j]))
    kwh17 <- raw$Demand_kWh[first[use]]
    kwh18 <- raw$Demand_kWh[second[use]]
    finite <- is.finite(kwh17) & is.finite(kwh18)
    use <- use[finite]
    if (!length(use)) next
    kwh <- kwh17[finite] + kwh18[finite]
    last <- tail(use, 1L)
    features$mean_peak_history_kwh[j] <- mean(kwh)
    features$most_recent_complete_peak_kwh[j] <- tail(kwh, 1L)
    features$pairs_count[j] <- length(use)
    features$latest_available_utc[j] <- format_utc(end[last])
    features$latest_source_row17[j] <- first[last]
    features$latest_source_row18[j] <- second[last]
    features$history_peak_source_pairs[j] <- pair_string(first[use], second[use])
    all_pairs <- all_pairs + length(use)
    min_cutoff_margin <- min(min_cutoff_margin, notice[j] - max(end[use]))
    min_window_start_margin <- min(min_window_start_margin, min(start[use]) - (notice[j] - lookback))
  }
}

# Independently enumerate source rows by date for fixed train/validation events.
# This uses neither the extraction's per-ID peak index nor its date matching.
fixed <- c(head(which(events$split == "train"), 3L), head(which(events$split == "validation"), 2L))
stopifnot(length(fixed) == 5L, !any(events$split[fixed] == "test"))
fixed_checks <- lapply(fixed, function(j) {
  household_rows <- which(raw$ID == events$ID[j] & raw$Participation_Phase == "Phase_2")
  times <- as.numeric(raw$From[household_rows])
  hours <- as.integer(as.character(raw$Hour[household_rows]))
  eligible <- household_rows[which(times >= notice[j] - lookback & times + 3600 <= notice[j] &
                                   hours %in% 17:18)]
  by_date <- split(eligible, as.character(raw$Date[eligible]))
  pairs <- lapply(by_date, function(r) {
    hh <- as.integer(as.character(raw$Hour[r]))
    if (length(r) != 2L || !setequal(hh, 17:18)) return(NULL)
    r <- r[order(hh)]
    if (diff(as.numeric(raw$From[r])) != 3600 || !all(is.finite(raw$Demand_kWh[r]))) return(NULL)
    r
  })
  pairs <- Filter(Negate(is.null), pairs)
  stopifnot(length(pairs) == features$pairs_count[j], length(pairs) > 0L)
  pairs <- do.call(rbind, pairs)
  pairs <- pairs[order(as.numeric(raw$From[pairs[, 2L]])), , drop = FALSE]
  expected <- raw$Demand_kWh[pairs[, 1L]] + raw$Demand_kWh[pairs[, 2L]]
  end <- as.numeric(raw$From[pairs[nrow(pairs), 2L]]) + 3600
  mean_difference <- abs(mean(expected) - features$mean_peak_history_kwh[j])
  recent_difference <- abs(tail(expected, 1L) - features$most_recent_complete_peak_kwh[j])
  stopifnot(mean_difference < 1e-12, recent_difference < 1e-12,
            pair_string(pairs[, 1L], pairs[, 2L]) == features$history_peak_source_pairs[j],
            format_utc(end) == features$latest_available_utc[j], end <= notice[j])
  list(ID = events$ID[j], Group = events$Group[j], Date = events$Date[j], split = events$split[j],
       pairs_count = length(expected), source_pairs = features$history_peak_source_pairs[j],
       latest_available_utc = format_utc(end), mean_absolute_difference_kwh = mean_difference,
       recent_absolute_difference_kwh = recent_difference)
})
stopifnot(all_pairs == sum(features$pairs_count), min_cutoff_margin >= 0,
          min_window_start_margin >= 0, identical(features[metadata], events))

# Keep the verification receipt writable with the existing base-R runtime.
json_value <- function(x) {
  if (is.list(x)) {
    values <- vapply(x, json_value, character(1))
    if (is.null(names(x))) return(paste0("[", paste(values, collapse = ","), "]"))
    keys <- encodeString(names(x), quote = '"')
    return(paste0("{", paste(paste0(keys, ":", values), collapse = ","), "}"))
  }
  if (is.na(x)) return("null")
  if (is.character(x)) return(encodeString(x, quote = '"'))
  if (is.logical(x)) return(if (x) "true" else "false")
  format(x, digits = 17L, scientific = FALSE, trim = TRUE)
}
split_counts <- as.list(table(features$split))
names(split_counts) <- names(table(features$split))
pair_counts <- as.list(table(features$pairs_count))
names(pair_counts) <- names(table(features$pairs_count))
receipt <- list(
  status = "passed", input_archive_md5 = archive_md5,
  prepared_metadata_csv_md5 = unname(tools::md5sum(prepared_path)),
  prepared_fields_read = as.list(metadata), output_rows = nrow(features), households = length(ids),
  split_counts = split_counts, pair_count_distribution = pair_counts, source_pairs_total = all_pairs,
  min_notice_minus_pair_end_seconds = min_cutoff_margin,
  min_pair_start_minus_lookback_start_seconds = min_window_start_margin,
  source_rows_are_one_based = TRUE, unique_ID_Date_Group_keys = TRUE,
  current_event_outcomes_used = FALSE, prior_experiment_history_retained = TRUE,
  fixed_raw_source_checks = fixed_checks
)
write.csv(features, features_path, row.names = FALSE, na = "", fileEncoding = "UTF-8")
receipt$features_csv_md5 <- unname(tools::md5sum(features_path))
writeLines(json_value(receipt), verification_path, useBytes = TRUE)
cat("PEAK_HISTORY", nrow(features), "rows;", all_pairs, "pairs; five raw-source checks passed\n")
