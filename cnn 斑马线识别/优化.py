import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, LearningRateScheduler
import os
import matplotlib.pyplot as plt

# 数据预处理
def prepare_data(train_dir, val_dir, img_size, batch_size):
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True
    )

    val_datagen = ImageDataGenerator(rescale=1./255)

    train_data = train_datagen.flow_from_directory(
        train_dir,
        target_size=(img_size, img_size),
        batch_size=batch_size,
        class_mode='binary'
    )

    val_data = val_datagen.flow_from_directory(
        val_dir,
        target_size=(img_size, img_size),
        batch_size=batch_size,
        class_mode='binary'
    )

    return train_data, val_data

# 构建 CNN 模型
def build_cnn_model(img_size):
    model = Sequential([
        Conv2D(32, (3, 3), activation='relu', input_shape=(img_size, img_size, 3)),
        MaxPooling2D(pool_size=(2, 2)),
        Conv2D(64, (3, 3), activation='relu'),
        MaxPooling2D(pool_size=(2, 2)),
        Conv2D(128, (3, 3), activation='relu'),
        MaxPooling2D(pool_size=(2, 2)),
        Flatten(),
        Dense(128, activation='relu'),
        Dropout(0.5),
        Dense(1, activation='sigmoid')
    ])

    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )

    return model

# 可视化训练结果
def plot_training_results(history):
    plt.figure(figsize=(14, 6))
    plt.subplot(1, 2, 1)
    plt.plot(history.history['accuracy'], label='训练集准确率', color='blue', marker='o')
    plt.plot(history.history['val_accuracy'], label='验证集准确率', color='orange', marker='x')
    plt.xlabel('Epochs', fontsize=12)
    plt.ylabel('Accuracy', fontsize=12)
    plt.title('训练和验证的准确率', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    for i, acc in enumerate(history.history['accuracy']):
        plt.text(i, acc, f'{acc:.2f}', ha='center', fontsize=8, color='blue')
    for i, val_acc in enumerate(history.history['val_accuracy']):
        plt.text(i, val_acc, f'{val_acc:.2f}', ha='center', fontsize=8, color='orange')
    plt.subplot(1, 2, 2)
    plt.plot(history.history['loss'], label='训练集损失', color='green', marker='o')
    plt.plot(history.history['val_loss'], label='验证集损失', color='red', marker='x')
    plt.xlabel('Epochs', fontsize=12)
    plt.ylabel('Loss', fontsize=12)
    plt.title('训练和验证的损失', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    for i, loss in enumerate(history.history['loss']):
        plt.text(i, loss, f'{loss:.2f}', ha='center', fontsize=8, color='green')
    for i, val_loss in enumerate(history.history['val_loss']):
        plt.text(i, val_loss, f'{val_loss:.2f}', ha='center', fontsize=8, color='red')
    plt.tight_layout()
    plt.show()

# 训练模型并添加回调函数
def train_model(model, train_data, val_data, epochs, output_path):
    early_stopping = EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True)
    model_checkpoint = ModelCheckpoint(filepath=os.path.join(output_path, 'zebra_crossing_cnn_model.h5'), save_best_only=True)
    lr_scheduler = LearningRateScheduler(lambda epoch: 1e-3 * 10**(-epoch / 20))

    history = model.fit(
        train_data,
        validation_data=val_data,
        epochs=epochs,
        callbacks=[early_stopping, model_checkpoint, lr_scheduler]
    )

    if not os.path.exists(output_path):
        os.makedirs(output_path)
    model.save(os.path.join(output_path, 'zebra_crossing_cnn_model.h5'))
    plot_training_results(history)

    return history

if __name__ == "__main__":
    train_dir = "E:/cnn 斑马线识别/train"
    val_dir = "E:/cnn 斑马线识别/val"
    img_size = 128
    batch_size = 32
    epochs = 50
    output_path = "./saved_model"

    train_data, val_data = prepare_data(train_dir, val_dir, img_size, batch_size)
    model = build_cnn_model(img_size)
    history = train_model(model, train_data, val_data, epochs, output_path)
    print("模型训练完成，已保存到", output_path)
