# Tab S6 worker setup

From the Mac, copy `tab/` to the tablet or clone this public repository, then run:

```sh
cd ~/haru-worker
bash tab/setup.sh
nano ~/haru-worker/worker.env
```

Add the required values to `worker.env`; it is created with mode `600`. To enable
automatic startup later, copy `tab/boot/start-haru` to `~/.termux/boot/start-haru`
and make it executable:

```sh
mkdir -p ~/.termux/boot
cp ~/haru-worker/tab/boot/start-haru ~/.termux/boot/start-haru
chmod 700 ~/.termux/boot/start-haru
```

Stop the worker with `tmux kill-session -t haru`. View the live session with
`tmux attach -t haru`, or inspect `~/haru-worker/haru.log` with `tail -f`.
