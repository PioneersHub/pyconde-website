from PIL import Image
import glob, os

cardspath = '/Users/terezaiofciu/Downloads/screening/twitter'

# original size : 2108 x 1054 300dpi
# youtube needs: 1920 x 1080 - 235 in width
#                1873  x 1054
# sparkle needs: 1280 x 720


#cardspath = "assets/static/media/"
# for sparkle and youtube the images in the twitter folder were not in the right size

print("Shrink images in the folder")
folder = cardspath+'/twitter'

for i in os.listdir(folder):
    file = f"{folder}/{i}"
    im = Image.open(file)

    width, height = im.size
    print( width, height)
    if (width == 2108) & (height == 1054) :
        # Setting the points for cropped image
        left = 125
        top = 0
        right = width - 110
        bottom = height

        # Setting the points for cropped image
        
      #  left = 115
      #  top = 28
     #   right = width - 120
      #  bottom = height - 28

        im1 = im.crop((left, top, right, bottom))

      #  im1.save(folder+"/youtube_7273x998/"+i , "png", dpi=(100,100))

        ### create sparkle thumbnail
        w, h = 1280, 720
        im2 = im1.resize((w, h), Image.ANTIALIAS)
        im2.save(folder+"/sparkle/"+i , "png", dpi=(100,100))
