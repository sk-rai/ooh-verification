#!/bin/bash
# Script to push to GitHub using SSH

cd /home/lynksavvy/projects/trustcapture

echo "Switching remote to SSH..."
git remote set-url origin git@github.com:sk-rai/ooh-verification.git

echo "Verifying remote..."
git remote -v

echo ""
echo "Pushing to GitHub..."
git push origin main

echo ""
echo "Done! Check status:"
git status
