# Independent source check: all-event metadata and five fixed train/validation
# numeric events only. No test outcome value is used or exported by this audit.
args <- commandArgs(trailingOnly=TRUE)
root <- normalizePath(args[[1]],winslash="/",mustWork=TRUE)
out <- file.path(root,"work/b1_real_response_data_20261103")
raw <- file.path(root,"data/public_datasets/挪威_iFlex_动态电价试验")
e <- new.env(parent=emptyenv());load(file.path(raw,"iFlex_dataset.RData"),envir=e)
a <- e$data_hourly;p <- e$participants
design <- read.csv(file.path(out,"selected_design.csv"),stringsAsFactors=FALSE)
header <- names(read.csv(file.path(out,"prepared_P_events.csv"),nrows=0,check.names=FALSE))
numeric_outcome_fields <- c("actual_day_kwh","actual_peak_2h_kwh","pre24_kwh","pre24_temperature","pre168_kwh")
classes <- rep(NA_character_,length(header));names(classes) <- header
classes[numeric_outcome_fields] <- "NULL"
prepared <- read.csv(file.path(out,"prepared_P_events.csv"),stringsAsFactors=FALSE,colClasses=classes,check.names=FALSE)
sample <- read.csv(file.path(out,"fixed_source_check_events.csv"),stringsAsFactors=FALSE)
stopifnot(!any(sample$split=="test"))
groups <- c("H2","Os_2","Trom_2")
ids <- as.character(p$ID[!is.na(p$Group_Phase2)&as.character(p$Group_Phase2)%in%groups])
idx <- which(as.character(a$Participation_Phase)=="Phase_2" & a$ID%in%ids)
# Metadata projection deliberately excludes Demand_kWh and all temperatures.
m <- a[idx,c("ID","From","Date","Hour","Price_signal","Experiment_price_NOK_kWh")]
m$.source_row <- idx
byid <- split(seq_len(nrow(m)),as.character(m$ID))
checks <- list();detail <- list();numeric <- list()
add <- function(name,bad) checks[[length(checks)+1L]] <<- data.frame(check=name,failures=as.integer(sum(bad)),stringsAsFactors=FALSE)
add("participant_ids_unique",length(ids)!=length(unique(ids)))
expected <- do.call(rbind,lapply(ids,function(id) {
  g <- as.character(p$Group_Phase2[as.character(p$ID)==id]);dd <- design[design$Group==g,]
  data.frame(ID=id,Group=g,Date=as.character(dd$Date),split=dd$split,signal=dd$Price_signal,stringsAsFactors=FALSE)
}))
makekey <- function(x) paste(x$ID,x$Date,sep="|")
add("expected_roster_missing_or_extra",c(!makekey(expected)%in%makekey(prepared),!makekey(prepared)%in%makekey(expected)))
add("duplicate_event_key",duplicated(makekey(prepared)))
prepared <- prepared[match(makekey(expected),makekey(prepared)),]
add("roster_group_split_signal",prepared$Group!=expected$Group|prepared$split!=expected$split|prepared$assigned_signal!=expected$signal)

for (id in ids) {
  x <- m[byid[[id]],];x <- x[order(x$From),]
  r <- which(prepared$ID==id)
  for (j in r) {
    z <- prepared[j,];date <- as.character(z$Date)
    notice <- as.numeric(as.POSIXct(paste(as.Date(date)-1,"17:00:00"),tz="UTC"))
    ev <- x[as.character(x$Date)==date,]
    hh <- as.integer(as.character(ev$Hour));peak <- ev[hh%in%c(17L,18L),]
    day_shape <- nrow(ev)==24L && setequal(hh,1:24) && !anyDuplicated(hh) && !anyDuplicated(ev$From)
    peak_shape <- nrow(peak)==2L && setequal(as.integer(as.character(peak$Hour)),17:18) && !anyDuplicated(peak$From)
    paths <- e$price_signals[as.character(e$price_signals$Price_signal)==z$assigned_signal,]
    price <- paths$Experiment_price_NOK_kWh[match(hh,as.integer(as.character(paths$Hour)))]
    price_match <- nrow(ev)>0 && all(is.finite(price)) && all(is.finite(ev$Experiment_price_NOK_kWh)) && all(abs(ev$Experiment_price_NOK_kWh-price)<1e-10)
    signal_match <- nrow(ev)>0 && all(!is.na(ev$Price_signal)) && all(as.character(ev$Price_signal)==z$assigned_signal)
    event_sources <- paste(ev$.source_row,collapse=";");peak_sources <- paste(peak$.source_row,collapse=";")
    event_clock <- all(as.integer(format(ev$From,"%H",tz="UTC"))+1L==hh) && all(as.character(as.Date(ev$From,tz="UTC"))==date)
    bad <- c(z$event_rows!=nrow(ev),z$peak_rows!=nrow(peak),z$complete_day&&!day_shape,z$complete_peak&&!peak_shape,
      z$signal_matches!=signal_match,z$price_matches!=price_match,z$event_source_rows!=event_sources,z$peak_source_rows!=peak_sources,
      !event_clock,as.numeric(as.POSIXct(z$notice_utc,tz="UTC",format="%Y-%m-%dT%H:%M:%SZ"))!=notice)
    history <- list()
    for (hours in c(24L,168L)) {
      tt <- as.numeric(x$From)
      sel <- which(tt>=notice-hours*3600 & tt+3600<=notice)
      times <- tt[sel]
      time_complete <- length(sel)==hours && length(unique(times))==hours && (length(times)<2 || all(diff(times)==3600))
      prefix <- paste0("pre",hours)
      last <- if(length(sel))times[length(sel)]+3600 else NA_real_
      saved_last <- as.numeric(as.POSIXct(z[[paste0(prefix,"_last_end_utc")]],tz="UTC",format="%Y-%m-%dT%H:%M:%SZ"))
      first_source <- if(length(sel))x$.source_row[sel[1]] else NA_integer_
      last_source <- if(length(sel))x$.source_row[tail(sel,1)] else NA_integer_
      bad <- c(bad,z[[paste0(prefix,"_rows")]]!=length(sel),
        if(is.na(last))!is.na(saved_last) else is.na(saved_last)||saved_last!=last,
        if(is.na(first_source))!is.na(z[[paste0(prefix,"_source_first")]]) else z[[paste0(prefix,"_source_first")]]!=first_source,
        if(is.na(last_source))!is.na(z[[paste0(prefix,"_source_last")]]) else z[[paste0(prefix,"_source_last")]]!=last_source,
        is.finite(last)&&last>notice)
      history[[prefix]] <- list(selected=sel,time_complete=time_complete)
    }
    detail[[length(detail)+1L]] <- data.frame(ID=id,Date=date,split=z$split,
      metadata_failures=sum(bad,na.rm=TRUE),metadata_NA=sum(is.na(bad)),
      day_time_complete=day_shape,peak_time_complete=peak_shape,
      pre24_time_complete=history$pre24$time_complete,pre168_time_complete=history$pre168$time_complete,
      price_match=price_match,signal_match=signal_match,stringsAsFactors=FALSE)
    if (any(sample$ID==id & sample$Date==date)) {
      # Only these five prespecified non-test numeric source events are read.
      er <- ev$.source_row;pr <- peak$.source_row
      row <- data.frame(ID=id,Date=date,split=z$split,
        actual_day_kwh=if(day_shape&&all(is.finite(a$Demand_kWh[er])))sum(a$Demand_kWh[er]) else NA_real_,
        actual_peak_2h_kwh=if(peak_shape&&all(is.finite(a$Demand_kWh[pr])))sum(a$Demand_kWh[pr]) else NA_real_,stringsAsFactors=FALSE)
      for(hours in c(24L,168L)) {
        prefix <- paste0("pre",hours);sel <- history[[prefix]]$selected;sr <- x$.source_row[sel]
        yy <- a$Demand_kWh[sr]
        row[[paste0(prefix,"_kwh")]] <- if(history[[prefix]]$time_complete&&all(is.finite(yy)))sum(yy) else NA_real_
        row[[paste0(prefix,"_finite")]] <- sum(is.finite(yy))
        if(hours==24L) {
          temp <- a$Temperature[sr]
          row$pre24_temperature <- if(history[[prefix]]$time_complete&&all(is.finite(temp)))mean(temp) else NA_real_
        }
      }
      numeric[[length(numeric)+1L]] <- row
    }
  }
}
detail <- do.call(rbind,detail)
add("all_event_metadata_match",detail$metadata_failures>0|detail$metadata_NA>0)
write.csv(expected,file.path(out,"independent_expected_roster.csv"),row.names=FALSE,fileEncoding="UTF-8")
write.csv(detail,file.path(out,"independent_metadata_checks.csv"),row.names=FALSE,fileEncoding="UTF-8")
write.csv(do.call(rbind,numeric),file.path(out,"independent_fixed_source_values.csv"),row.names=FALSE,na="",fileEncoding="UTF-8")
write.csv(do.call(rbind,checks),file.path(out,"independent_source_check_summary.csv"),row.names=FALSE,fileEncoding="UTF-8")
cat("SOURCE_CHECK_EVENTS",nrow(detail),"FIXED_NUMERIC_EVENTS",length(numeric),"METADATA_FAILURES",sum(detail$metadata_failures),"\n")
