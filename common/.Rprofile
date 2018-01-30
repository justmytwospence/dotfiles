.libPaths(c(file.path(Sys.getenv("SPARK_HOME"), "R", "lib"), .libPaths()))

if (interactive()) {

    options(tibble.print_min=30)

    ## timestamp for prompt
    library(tcltk2)
    tclTaskSchedule(1000, { options(prompt=paste(format(Sys.time(), "%H:%M:%S"), "> ")) },
                    id="ticktock", redo=TRUE)

    ## not Emacs
    if (Sys.getenv("EMACS") != "t") {
        ## colored output
        options(colorout.verbose=1)
        library(colorout)
        setOutputColors256(const=255, date=6, error=1, negnum=21, normal=0,
                           number=4, stderror=1, string=2, warn=3)
    }
}

source("~/.Rprofile_local")
