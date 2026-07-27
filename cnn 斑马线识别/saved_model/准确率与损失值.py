from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import load_model

# 替换路径为你的模型文件位置
model = load_model('E:/cnn 斑马线识别/saved_model/zebra_crossing_cnn_model.h5')

# 测试数据路径
test_dir = "E:/cnn 斑马线识别/val"  # 替换为测试数据的路径
img_size = 128  # 图像大小
batch_size = 32

# 数据预处理
test_datagen = ImageDataGenerator(rescale=1./255)
test_data = test_datagen.flow_from_directory(
    test_dir,
    target_size=(img_size, img_size),
    batch_size=batch_size,
    class_mode='binary'
)

# 在测试集上评估模型
loss, accuracy = model.evaluate(test_data)
print(f"测试集上的损失: {loss}")
print(f"测试集上的准确率: {accuracy}")
